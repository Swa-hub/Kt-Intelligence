"""Project overview generator.

Produces a grounded, module-by-module explanation of what's been
ingested. Uses the same cite-only-what-was-retrieved discipline as
the gap detector.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

from . import demo_data, nebius_client
from .db import connect
from .retrieval import format_evidence_block, Hit


OVERVIEW_SYSTEM = """You are the Project Overview writer in KT Intelligence.
Produce a concise overview grounded in the EVIDENCE chunks provided.

Rules:
- Cite only files that appear in the evidence. Do not invent paths.
- If evidence does not cover a question, write "the uploaded sources do
  not describe this" — do not guess.
- Keep the overview compact and useful for an onboarding developer.

Return JSON with:
  purpose: 1-2 sentences on what the project is for
  stack: array of strings, each a technology mentioned in the evidence
  entry_points: array of {filename, note}
  modules: array of {name, purpose, files: [filename], notes}
  open_questions: array of strings — things an incoming dev should ask
Return ONLY the JSON object."""


def _file_sample(project_id: int, limit: int = 20) -> list[Hit]:
    """Pick a representative set of chunks across sources."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.id, c.source_id, c.kind, c.text, c.start_line, c.end_line, s.filename "
            "FROM chunks c JOIN sources s ON s.id = c.source_id "
            "WHERE c.project_id = ? ORDER BY c.id ASC",
            [project_id],
        ).fetchall()

    # Prefer the first chunk per source (usually module docstring or opening),
    # then round-robin through additional chunks.
    by_source: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_source[r["source_id"]].append(r)

    picked: list[dict] = []
    # First pass: first chunk from each source
    for src_rows in by_source.values():
        picked.append(src_rows[0])
    # Second pass: additional context, round-robin
    i = 1
    while len(picked) < limit:
        added = False
        for src_rows in by_source.values():
            if i < len(src_rows):
                picked.append(src_rows[i])
                added = True
                if len(picked) >= limit:
                    break
        if not added:
            break
        i += 1

    return [
        Hit(
            chunk_id=r["id"], source_id=r["source_id"], filename=r["filename"],
            kind=r["kind"], text=r["text"], start_line=r["start_line"] or 0,
            end_line=r["end_line"] or 0, score=0.0,
        )
        for r in picked
    ]


def generate(project_id: int) -> dict:
    hits = _file_sample(project_id)
    if not hits:
        return {"error": "No sources ingested yet."}
    if nebius_client.demo_mode():
        return demo_data.overview()
    evidence = format_evidence_block(hits)
    content = nebius_client.chat(
        [
            {"role": "system", "content": OVERVIEW_SYSTEM},
            {"role": "user", "content": f"EVIDENCE:\n{evidence}\n\nReturn the JSON object."},
        ],
        temperature=0.1,
        max_tokens=900,
    )
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return {"raw": content, "parse_error": True}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"raw": content, "parse_error": True}
    # Strip any invented files
    valid_files = {h.filename for h in hits}
    for m in parsed.get("modules", []) or []:
        m["files"] = [f for f in (m.get("files") or []) if f in valid_files]
    parsed["entry_points"] = [
        e for e in (parsed.get("entry_points") or []) if e.get("filename") in valid_files
    ]
    return parsed
