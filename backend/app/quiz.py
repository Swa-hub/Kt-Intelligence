"""Quiz generator for the Tutor.

Generates short multiple-choice questions grounded in retrieved evidence.
No persistent attempt tracking in the MVP — the frontend scores locally.
"""
from __future__ import annotations

import json
import re

from . import demo_data, nebius_client
from .retrieval import format_evidence_block, search


QUIZ_SYSTEM = """You are the Quiz Writer inside KT Intelligence.
Write short multiple-choice questions grounded in the EVIDENCE provided.

Rules:
- Every question must be answerable from the evidence; cite it with [n].
- Each question has exactly 4 options; exactly one is correct.
- Keep options plausible but unambiguous given the evidence.
- Prefer concrete questions (file/function behaviour) over trivia.

Return JSON with:
  questions: array of {
    question: string,
    options: array of 4 strings,
    correct_index: 0..3,
    explanation: 1-2 sentences,
    evidence_refs: array of {filename, start_line, end_line}
  }
Return ONLY the JSON object."""


def generate(project_id: int, topic: str, n: int = 3) -> dict:
    hits = search(project_id, topic, k=8)
    if not hits:
        return {"questions": [], "note": "No evidence found for that topic."}
    if nebius_client.demo_mode():
        return demo_data.quiz(topic)
    evidence = format_evidence_block(hits)
    content = nebius_client.chat(
        [
            {"role": "system", "content": QUIZ_SYSTEM},
            {"role": "user", "content": f"TOPIC: {topic}\n\nEVIDENCE:\n{evidence}\n\nWrite {n} questions."},
        ],
        temperature=0.3,
        max_tokens=1200,
    )
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return {"raw": content, "parse_error": True}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"raw": content, "parse_error": True}

    valid_files = {h.filename for h in hits}
    cleaned = []
    for q in parsed.get("questions", []) or []:
        if not isinstance(q.get("options"), list) or len(q["options"]) != 4:
            continue
        if not isinstance(q.get("correct_index"), int) or not (0 <= q["correct_index"] <= 3):
            continue
        q["evidence_refs"] = [r for r in (q.get("evidence_refs") or []) if r.get("filename") in valid_files]
        cleaned.append(q)
    return {"questions": cleaned}
