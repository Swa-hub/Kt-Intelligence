"""Track content hashes on re-upload and flag memory records that may
reference stale evidence."""
from __future__ import annotations

import hashlib
import json

from .db import connect, now_iso


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def previous_source(project_id: int, filename: str) -> dict | None:
    """Return the current (non-superseded) source with this filename, if any."""
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM sources WHERE project_id = ? AND filename = ? AND superseded_by IS NULL ORDER BY id DESC LIMIT 1",
            [project_id, filename],
        ).fetchone()


def mark_superseded(old_id: int, new_id: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE sources SET superseded_by = ? WHERE id = ?",
            [new_id, old_id],
        )


def flag_memory_for_file(project_id: int, filename: str) -> list[int]:
    """Mark memory records that cite the changed file as 'conflicting' so a
    human reviews whether they're still true. Returns affected record ids
    and logs the drift as a verification_events row."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, verification_status, sources_json FROM memory_records WHERE project_id = ? AND verification_status IN ('verified','unverified','ai_suggested')",
            [project_id],
        ).fetchall()
    affected: list[tuple[int, str]] = []
    for r in rows:
        srcs = json.loads(r["sources_json"] or "[]")
        if any((s or {}).get("filename") == filename for s in srcs):
            affected.append((r["id"], r["verification_status"]))
    if affected:
        now = now_iso()
        with connect() as conn:
            for rid, prev in affected:
                conn.execute(
                    "UPDATE memory_records SET verification_status = 'conflicting', updated_at = ? WHERE id = ?",
                    [now, rid],
                )
                conn.execute(
                    "INSERT INTO verification_events(project_id, record_id, from_status, to_status, reason, actor, created_at) VALUES (?, ?, ?, 'conflicting', ?, 'system', ?)",
                    [project_id, rid, prev, f"Source file '{filename}' changed — knowledge may be stale.", now],
                )
    return [rid for rid, _ in affected]
