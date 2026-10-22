"""Personal KT Tutor — grounded Q&A over the project's sources."""
from __future__ import annotations

from . import demo_data, nebius_client
from .db import connect, dumps, now_iso
from .retrieval import search, format_evidence_block


LEVELS = {
    "beginner": "Explain as if the developer joined the project today. Define jargon. Prefer short paragraphs and concrete examples.",
    "intermediate": "Assume the developer is familiar with the stack but new to this project. Skip basics, show the flow.",
    "advanced": "Assume senior-level familiarity. Focus on edge cases, failure modes, and non-obvious trade-offs.",
}

SYSTEM_PROMPT = """You are the Personal KT Tutor inside KT Intelligence.
You help a developer understand a specific project using only the EVIDENCE
chunks provided from that project's uploaded sources.

Hard rules:
- Base factual claims only on the evidence. If evidence doesn't cover
  something, say "the uploaded sources don't contain this" — do not guess.
- Cite evidence inline with bracketed numbers like [1], [2] that match the
  evidence chunks. Do not invent file paths or line numbers.
- Distinguish verified facts from your interpretation. Prefix interpretive
  sentences with "Likely" or "Appears to".
- Keep answers tight; prefer bullet points when listing files or steps.
"""


def answer(project_id: int, question: str, level: str = "intermediate") -> dict:
    hits = search(project_id, question, k=6)
    if nebius_client.demo_mode():
        demo = demo_data.chat_answer(question)
        content = demo["answer"]
        citations = [h.as_dict() for h in hits] or demo["citations"]
        with connect() as conn:
            conn.execute(
                "INSERT INTO chat_messages(project_id, role, content, citations_json, created_at) VALUES (?, 'user', ?, NULL, ?)",
                (project_id, question, now_iso()),
            )
            conn.execute(
                "INSERT INTO chat_messages(project_id, role, content, citations_json, created_at) VALUES (?, 'assistant', ?, ?, ?)",
                (project_id, content, dumps(citations), now_iso()),
            )
        return {"answer": content, "citations": citations, "level": level, "demo": True}

    evidence_block = format_evidence_block(hits) if hits else "[no evidence retrieved]"
    level_note = LEVELS.get(level, LEVELS["intermediate"])

    user = (
        f"Learning level: {level}. {level_note}\n\n"
        f"Question: {question}\n\n"
        f"EVIDENCE:\n{evidence_block}\n\n"
        "Answer the question. Cite evidence with [n]. If the evidence doesn't "
        "answer the question, say so and suggest which file to upload."
    )
    content = nebius_client.chat(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        temperature=0.3,
        max_tokens=900,
    )
    citations = [h.as_dict() for h in hits]
    with connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages(project_id, role, content, citations_json, created_at) VALUES (?, 'user', ?, NULL, ?)",
            (project_id, question, now_iso()),
        )
        conn.execute(
            "INSERT INTO chat_messages(project_id, role, content, citations_json, created_at) VALUES (?, 'assistant', ?, ?, ?)",
            (project_id, content, dumps(citations), now_iso()),
        )
    return {"answer": content, "citations": citations, "level": level}


def history(project_id: int, limit: int = 50) -> list[dict]:
    import json as _json
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE project_id = ? ORDER BY id ASC LIMIT ?",
            [project_id, limit],
        ).fetchall()
    for r in rows:
        r["citations"] = _json.loads(r.pop("citations_json") or "null")
    return rows


def learning_progress(project_id: int) -> dict:
    """Lightweight learner model: distinct files cited back to the user and
    rough question counts over time. Not a full progress graph — just enough
    to show the learner what they've already covered."""
    import json as _json
    import re as _re
    from collections import Counter

    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content, citations_json, created_at FROM chat_messages "
            "WHERE project_id = ? ORDER BY id ASC",
            [project_id],
        ).fetchall()

    user_turns = [r for r in rows if r["role"] == "user"]
    assistant_turns = [r for r in rows if r["role"] == "assistant"]

    files_covered: Counter = Counter()
    for r in assistant_turns:
        cites = _json.loads(r.get("citations_json") or "[]") or []
        for c in cites:
            fn = (c or {}).get("filename")
            if fn:
                files_covered[fn] += 1

    # Rough topic clusters from user prompts: extract notable code-ish tokens
    topic_counter: Counter = Counter()
    for r in user_turns:
        for tok in _re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", r["content"]):
            if tok.lower() in {"what", "which", "how", "does", "this", "that", "project", "code"}:
                continue
            topic_counter[tok] += 1

    # Quiz performance per topic — real learner signal.
    with connect() as conn:
        qrows = conn.execute(
            "SELECT topic, correct FROM quiz_attempts WHERE project_id = ?",
            [project_id],
        ).fetchall()
    quiz_by_topic: dict[str, dict[str, int]] = {}
    for q in qrows:
        t = q["topic"]
        d = quiz_by_topic.setdefault(t, {"attempts": 0, "correct": 0})
        d["attempts"] += 1
        d["correct"] += int(q["correct"])
    quiz_summary = [
        {
            "topic": t,
            "attempts": d["attempts"],
            "correct": d["correct"],
            "accuracy": round(d["correct"] / d["attempts"], 2) if d["attempts"] else 0.0,
        }
        for t, d in sorted(quiz_by_topic.items(), key=lambda kv: kv[1]["attempts"], reverse=True)
    ]
    # Only call a topic weak after enough attempts to be meaningful.
    # One wrong answer in a 3-question set shouldn't surface a nudge.
    weak_topics = [q["topic"] for q in quiz_summary if q["attempts"] >= 5 and q["accuracy"] < 0.6]

    return {
        "questions_asked": len(user_turns),
        "answers_received": len(assistant_turns),
        "files_covered": [{"filename": f, "times_cited": n} for f, n in files_covered.most_common(10)],
        "frequent_topics": [t for t, _ in topic_counter.most_common(8)],
        "quiz_by_topic": quiz_summary,
        "weak_topics": weak_topics,
    }
