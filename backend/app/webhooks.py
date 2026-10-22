"""GitHub webhook receiver.

Flow:
  1. Verify HMAC signature (if GITHUB_WEBHOOK_SECRET is set).
  2. On a push event, pull the updated versions of changed files from
     the repository tarball and re-ingest them. change_detection.py
     handles supersede + conflicting-memory flagging automatically.
  3. Post a Slack notice if SLACK_WEBHOOK_URL is set.
  4. Return a drift report with affected memory + findings.

Points this project at a GitHub repo via the `project.id` <-> repo mapping
is intentionally kept out of the MVP: the endpoint accepts an explicit
`project_id` in the URL so a single KT Intelligence instance can serve
many projects, each with their own repository.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import logging
import shutil
import tarfile
import urllib.request
from pathlib import Path

from .config import settings
from .db import connect
from .drift import affected_memory, pr_comment_markdown, related_findings
from .github_import import INGEST_EXTENSIONS, SKIP_DIRS, parse_github_url, _fetch_tarball
from .ingestion import save_source_and_chunks
from . import notifications

log = logging.getLogger(__name__)


class WebhookError(RuntimeError):
    pass


def verify_signature(body: bytes, signature_header: str | None) -> bool:
    """Return True if signature matches, or if no secret is configured."""
    secret = settings.github_webhook_secret
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def handle_push(project_id: int, payload: dict) -> dict:
    """Re-ingest files touched by the push and return a drift report."""
    repo_full = (payload.get("repository") or {}).get("full_name")
    ref = payload.get("ref", "")  # refs/heads/<branch>
    branch = ref.rsplit("/", 1)[-1] if ref else None
    commits = payload.get("commits") or []
    changed: set[str] = set()
    for c in commits:
        for key in ("added", "modified"):
            for p in (c.get(key) or []):
                changed.add(p)
    changed_files = sorted(changed)

    if not repo_full or "/" not in repo_full:
        raise WebhookError("payload missing repository.full_name")

    with connect() as conn:
        proj = conn.execute("SELECT id, name FROM projects WHERE id = ?", [project_id]).fetchone()
    if not proj:
        raise WebhookError(f"project {project_id} not found")

    owner, repo = repo_full.split("/", 1)
    # Re-fetch the tarball and extract just the changed, ingestable files.
    try:
        data = _fetch_tarball(owner, repo, branch)
    except Exception as e:
        raise WebhookError(f"could not fetch tarball: {e}")

    target_dir = Path(settings.upload_dir) / f"project_{project_id}" / f"gh_{owner}_{repo}"
    target_dir.mkdir(parents=True, exist_ok=True)

    ingested: list[dict] = []
    import io as _io
    with tarfile.open(fileobj=_io.BytesIO(data), mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            parts = Path(member.name).parts[1:]
            if not parts:
                continue
            rel = "/".join(parts)
            if rel not in changed:
                continue
            if any(p in SKIP_DIRS for p in parts):
                continue
            if Path(rel).suffix.lower() not in INGEST_EXTENSIONS:
                continue
            extracted = tf.extractfile(member)
            if not extracted:
                continue
            content = extracted.read()
            safe = rel.replace("/", "__")
            dest = target_dir / safe
            dest.write_bytes(content)
            try:
                res = save_source_and_chunks(project_id, rel, dest, None, origin=f"github:{owner}/{repo}")
                ingested.append(res)
            except Exception as e:
                log.warning("re-ingest failed for %s: %s", rel, e)

    mem_hits = affected_memory(project_id, changed_files)
    find_hits = related_findings(project_id, changed_files)

    # Fire-and-forget Slack notice
    try:
        if mem_hits or find_hits:
            notifications.drift_notice(project_id, proj["name"], changed_files, len(mem_hits))
    except Exception as e:
        log.warning("slack notify failed: %s", e)

    return {
        "repo": repo_full,
        "branch": branch,
        "changed_files": changed_files,
        "ingested": ingested,
        "affected_memory": mem_hits,
        "related_findings": find_hits,
        "comment_markdown": pr_comment_markdown(project_id, proj["name"], changed_files, settings.public_base_url or None),
    }
