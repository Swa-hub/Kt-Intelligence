"""Drift report + PR comment markdown generator.

Used by:
  - the GitHub webhook (`webhooks.py`) when a push lands
  - a GitHub Action calling `/api/projects/{id}/pr-comment` directly
"""
from __future__ import annotations

import json

from .db import connect


def affected_memory(project_id: int, changed_files: list[str]) -> list[dict]:
    """Memory records whose sources reference any of the changed files."""
    if not changed_files:
        return []
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, topic, verification_status, sources_json, updated_at "
            "FROM memory_records WHERE project_id = ?",
            [project_id],
        ).fetchall()
    out = []
    for r in rows:
        srcs = json.loads(r["sources_json"] or "[]")
        hits = [s for s in srcs if s and s.get("filename") in changed_files]
        if hits:
            r["matched_sources"] = hits
            out.append(r)
    return out


def related_findings(project_id: int, changed_files: list[str]) -> list[dict]:
    """Open findings whose code evidence references any of the changed files."""
    if not changed_files:
        return []
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, title, severity, status, code_evidence_json "
            "FROM findings WHERE project_id = ? AND status IN ('open','awaiting')",
            [project_id],
        ).fetchall()
    out = []
    for r in rows:
        ev = json.loads(r["code_evidence_json"] or "[]")
        if any((e or {}).get("filename") in changed_files for e in ev):
            out.append(r)
    return out


def pr_comment_markdown(project_id: int, project_name: str, changed_files: list[str], public_url: str | None = None) -> str:
    memory_hits = affected_memory(project_id, changed_files)
    finding_hits = related_findings(project_id, changed_files)

    if not memory_hits and not finding_hits:
        return (
            f"### KT Intelligence · {project_name}\n\n"
            "No verified knowledge or open findings reference the changed files. "
            "Safe from a knowledge-drift standpoint.\n"
        )

    lines = [f"### :warning: KT Intelligence · {project_name}", ""]
    lines.append(f"This PR touches **{len(changed_files)}** file(s) that KT Intelligence has knowledge about.")
    lines.append("")

    if memory_hits:
        lines.append(f"**{len(memory_hits)} memory record(s) may need re-verification**")
        lines.append("")
        for m in memory_hits[:8]:
            cites = ", ".join(f"`{s.get('filename')}`" for s in m["matched_sources"])
            lines.append(f"- `[{m['verification_status']}]` **{m['topic']}** — cites {cites}")
        if len(memory_hits) > 8:
            lines.append(f"- …and {len(memory_hits) - 8} more")
        lines.append("")

    if finding_hits:
        lines.append(f"**{len(finding_hits)} open finding(s) reference the changed files**")
        lines.append("")
        for f in finding_hits[:8]:
            lines.append(f"- `[{f['severity']}]` {f['title']}")
        if len(finding_hits) > 8:
            lines.append(f"- …and {len(finding_hits) - 8} more")
        lines.append("")

    lines.append("A reviewer should decide whether the referenced knowledge is still accurate after this change.")
    if public_url:
        lines.append("")
        lines.append(f"[Open the Project Memory →]({public_url}/projects/{project_id}/memory)")
    return "\n".join(lines)


def attention_feed(project_id: int) -> dict:
    """Everything on this project that currently needs human attention,
    in one editorial list for the UI."""
    with connect() as conn:
        gaps = conn.execute(
            "SELECT id, title, severity, category, status, created_at FROM findings "
            "WHERE project_id = ? AND status IN ('open','awaiting') "
            "ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, created_at DESC",
            [project_id],
        ).fetchall()
        mem = conn.execute(
            "SELECT id, topic, verification_status, updated_at FROM memory_records "
            "WHERE project_id = ? AND verification_status IN ('unverified','conflicting','ai_suggested') "
            "ORDER BY CASE verification_status WHEN 'conflicting' THEN 0 WHEN 'ai_suggested' THEN 1 ELSE 2 END, updated_at DESC",
            [project_id],
        ).fetchall()
    return {"open_findings": gaps, "memory_needs_review": mem}
