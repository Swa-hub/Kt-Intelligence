"""Import a public GitHub repository as sources.

Uses the codeload tarball endpoint over HTTPS, so no git CLI is required
on the host. Only public repos are supported in the MVP.
"""
from __future__ import annotations

import io
import re
import shutil
import tarfile
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

from .config import settings
from .ingestion import CODE_EXTENSIONS, DOC_EXTENSIONS, save_source_and_chunks

# File patterns we never ingest regardless of extension.
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".cache"}
INGEST_EXTENSIONS = CODE_EXTENSIONS | DOC_EXTENSIONS | {".yml", ".yaml", ".toml", ".ini", ".cfg"}
MAX_FILE_BYTES = 400_000       # per-file hard cap
MAX_FILES_PER_REPO = 150       # cap total ingested files
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024


_url_re = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?(?:/tree/([^/]+))?/?$"
)


class GitHubImportError(RuntimeError):
    pass


def parse_github_url(url: str) -> tuple[str, str, str | None]:
    m = _url_re.match(url.strip())
    if not m:
        raise GitHubImportError("That URL doesn't look like a GitHub repo (expected github.com/owner/repo).")
    owner, repo, branch = m.group(1), m.group(2), m.group(3)
    return owner, repo, branch


def _fetch_tarball(owner: str, repo: str, branch: str | None) -> bytes:
    """Try the given branch; if omitted, try main then master."""
    candidates = [branch] if branch else ["main", "master"]
    last_err: Exception | None = None
    for b in candidates:
        url = f"https://codeload.github.com/{owner}/{repo}/tar.gz/refs/heads/{b}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = resp.read(MAX_ARCHIVE_BYTES + 1)
                if len(data) > MAX_ARCHIVE_BYTES:
                    raise GitHubImportError(f"Repository tarball exceeds {MAX_ARCHIVE_BYTES // (1024*1024)} MB limit.")
                return data
        except HTTPError as e:
            if e.code == 404:
                last_err = e
                continue
            raise GitHubImportError(f"GitHub returned {e.code}: {e.reason}")
        except URLError as e:
            raise GitHubImportError(f"Network error reaching GitHub: {e}")
    raise GitHubImportError(f"Could not find a tarball for {owner}/{repo} (tried {', '.join(candidates)}). If the default branch isn't main/master, append /tree/<branch> to the URL.")


def _should_ingest(path_parts: tuple[str, ...], size: int) -> bool:
    if any(p in SKIP_DIRS for p in path_parts):
        return False
    if size > MAX_FILE_BYTES:
        return False
    name = path_parts[-1]
    ext = Path(name).suffix.lower()
    return ext in INGEST_EXTENSIONS


def import_repo(project_id: int, url: str) -> dict:
    owner, repo, branch = parse_github_url(url)
    data = _fetch_tarball(owner, repo, branch)
    results: list[dict] = []
    skipped = 0
    target_dir = Path(settings.upload_dir) / f"project_{project_id}" / f"gh_{owner}_{repo}"
    if target_dir.exists():
        shutil.rmtree(target_dir, ignore_errors=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            # Strip the top-level "<repo>-<sha>/" directory
            parts = Path(member.name).parts[1:]
            if not parts:
                continue
            if not _should_ingest(parts, member.size):
                skipped += 1
                continue
            if len(results) >= MAX_FILES_PER_REPO:
                skipped += 1
                continue
            try:
                extracted = tf.extractfile(member)
                if not extracted:
                    continue
                content = extracted.read()
            except Exception:
                skipped += 1
                continue
            rel = "/".join(parts)
            safe_name = rel.replace("/", "__")
            dest = target_dir / safe_name
            dest.write_bytes(content)
            try:
                res = save_source_and_chunks(project_id, rel, dest, declared_kind=None, origin=f"github:{owner}/{repo}")
                results.append(res)
            except Exception:
                skipped += 1

    return {
        "repo": f"{owner}/{repo}",
        "branch": branch or "default",
        "files_ingested": len(results),
        "files_skipped": skipped,
        "sources": results,
    }
