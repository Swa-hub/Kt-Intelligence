"""Persistent Project Memory.

Records are never silently overwritten. When new content for the same topic
arrives, the existing record is marked 'conflicting' or 'outdated' and a new
one is added, so a human can resolve.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .db import connect, dumps, now_iso


VALID_STATUSES = {"verified", "unverified", "ai_suggested", "conflicting", "outdated"}

# Words that add no identifying value and should drop out of the topic key.
_STOPWORDS = {
    "a", "an", "the", "of", "on", "at", "in", "to", "for", "with", "and",
    "or", "is", "are", "was", "were", "be", "this", "that", "it", "its",
    "api", "handler", "route", "function", "method", "class",
}

# Collapse common tech synonyms to the same canonical form so that
# "auth on get_order" and "get_order authentication" normalise to the same key.
_SYNONYMS = {
    "authentication": "auth", "authenticated": "auth", "authorise": "auth",
    "authorize": "auth", "authorisation": "auth", "authorization": "auth",
    "login": "auth", "logins": "auth",
    "repository": "repo", "repositories": "repo",
    "configuration": "config", "configure": "config",
    "deployment": "deploy", "deploying": "deploy", "deployed": "deploy",
    "idempotency": "idempotent", "idempotence": "idempotent",
    "retries": "retry", "retrying": "retry",
    "endpoints": "endpoint",
    "docs": "documentation",
}


def normalise_topic(topic: str) -> str:
    """Normalise for conflict detection: lowercase, strip punctuation,
    drop stopwords, apply light synonym folding, sort. Two topics with
    the same key are treated as the same thing."""
    cleaned = re.sub(r"[^A-Za-z0-9_/\.\s-]", " ", (topic or "").lower())
    tokens = []
    for t in cleaned.split():
        if not t or t in _STOPWORDS:
            continue
        tokens.append(_SYNONYMS.get(t, t))
    # Deduplicate while sorting.
    return " ".join(sorted(set(tokens)))


def _log_event(conn, project_id: int, record_id: int, from_status: str | None, to_status: str, reason: str, actor: str = "system") -> None:
    conn.execute(
        "INSERT INTO verification_events(project_id, record_id, from_status, to_status, reason, actor, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, record_id, from_status, to_status, reason, actor, now_iso()),
    )


def create_record(
    project_id: int,
    topic: str,
    content: str,
    verification_status: str = "unverified",
    sources: list[dict] | None = None,
    confidence: float | None = None,
) -> dict:
    if verification_status not in VALID_STATUSES:
        raise ValueError(f"invalid verification_status: {verification_status}")
    key = normalise_topic(topic)
    with connect() as conn:
        prior = conn.execute(
            "SELECT id, verification_status, topic FROM memory_records "
            "WHERE project_id = ? AND topic_key = ? AND verification_status NOT IN ('outdated','conflicting')",
            [project_id, key],
        ).fetchall()
        for row in prior:
            new_status = "outdated" if row["verification_status"] == "ai_suggested" else "conflicting"
            conn.execute(
                "UPDATE memory_records SET verification_status = ?, updated_at = ? WHERE id = ?",
                (new_status, now_iso(), row["id"]),
            )
            _log_event(
                conn, project_id, row["id"], row["verification_status"], new_status,
                f"Superseded by new record on topic '{topic}' (same normalised key as '{row['topic']}')",
                actor="system",
            )
        cur = conn.execute(
            "INSERT INTO memory_records(project_id, topic, topic_key, content, verification_status, sources_json, confidence, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, topic, key, content, verification_status, dumps(sources or []), confidence, now_iso(), now_iso()),
        )
        new_id = cur.lastrowid
        _log_event(conn, project_id, new_id, None, verification_status, "Record created", actor="user")
        row = conn.execute("SELECT * FROM memory_records WHERE id = ?", [new_id]).fetchone()
    row["sources"] = json.loads(row.pop("sources_json") or "null")
    return row


def list_records(project_id: int, query: str | None = None, status: str | None = None) -> list[dict]:
    sql = "SELECT * FROM memory_records WHERE project_id = ?"
    params: list[Any] = [project_id]
    if status:
        sql += " AND verification_status = ?"
        params.append(status)
    if query:
        sql += " AND (topic LIKE ? OR content LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like])
    sql += " ORDER BY updated_at DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    for r in rows:
        r["sources"] = json.loads(r.pop("sources_json") or "null")
    return rows


def update_status(record_id: int, status: str, *, reason: str = "", actor: str = "user") -> dict | None:
    if status not in VALID_STATUSES:
        raise ValueError("invalid status")
    with connect() as conn:
        existing = conn.execute("SELECT project_id, verification_status FROM memory_records WHERE id = ?", [record_id]).fetchone()
        if not existing:
            return None
        conn.execute(
            "UPDATE memory_records SET verification_status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), record_id),
        )
        _log_event(conn, existing["project_id"], record_id, existing["verification_status"], status, reason or f"Marked {status}", actor=actor)
        row = conn.execute("SELECT * FROM memory_records WHERE id = ?", [record_id]).fetchone()
    row["sources"] = json.loads(row.pop("sources_json") or "null")
    return row


def events_for(record_id: int) -> list[dict]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM verification_events WHERE record_id = ? ORDER BY id DESC",
            [record_id],
        ).fetchall()
