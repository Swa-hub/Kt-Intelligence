"""Outbound notifications (currently Slack via incoming-webhook).

Posting is a best-effort fire-and-forget. Failures are logged but never
block the request that triggered them.
"""
from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

from .config import settings

log = logging.getLogger(__name__)


def enabled() -> bool:
    return bool(settings.slack_webhook_url)


def post(text: str, *, blocks: list | None = None) -> bool:
    if not enabled():
        return False
    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        settings.slack_webhook_url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            resp.read()
        return True
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
        log.warning("slack post failed: %s", e)
        return False


def project_link(project_id: int, section: str = "") -> str:
    if not settings.public_base_url:
        return f"(project {project_id})"
    base = settings.public_base_url.rstrip("/")
    tail = f"/{section}" if section else ""
    return f"{base}/projects/{project_id}{tail}"


def analysis_summary(project_id: int, project_name: str, findings_created: int, high_count: int) -> None:
    if not enabled():
        return
    link = project_link(project_id, "gaps")
    text = (
        f":mag: KT Intelligence · *{project_name}*\n"
        f"Gap analysis recorded *{findings_created}* finding{'s' if findings_created != 1 else ''}"
        + (f", including *{high_count} high severity*." if high_count else ".")
    )
    post(f"{text}\n<{link}|Open findings →>")


def drift_notice(project_id: int, project_name: str, changed_files: list[str], affected_records: int) -> None:
    if not enabled():
        return
    files = ", ".join(f"`{f}`" for f in changed_files[:6])
    more = f" (+{len(changed_files)-6} more)" if len(changed_files) > 6 else ""
    link = project_link(project_id, "memory")
    text = (
        f":warning: KT Intelligence · *{project_name}* — source drift detected\n"
        f"Changed: {files}{more}\n"
        f"Flagged *{affected_records}* memory record{'s' if affected_records != 1 else ''} as conflicting for review.\n"
        f"<{link}|Review memory →>"
    )
    post(text)
