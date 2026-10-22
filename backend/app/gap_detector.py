"""KT Gap and Contradiction Detector.

Approach:
  1. From transcript/doc chunks, extract candidate claims (statements that
     assert how the system behaves).
  2. For each claim, retrieve the most relevant code evidence via BM25.
  3. Ask the model to classify the claim against the code evidence and emit
     a structured finding. The model is instructed never to invent file
     paths — it may only cite the retrieved chunks.
"""
from __future__ import annotations

import json
import re
from typing import Any

import logging

from . import demo_data, nebius_client, notifications
from .db import connect, dumps, now_iso
from .retrieval import Hit, search, format_evidence_block

log = logging.getLogger(__name__)

# Last call's extraction method so analysis responses can report it.
# "llm" means the model-based extractor succeeded, "regex" means fallback.
_LAST_METHOD = {"method": "unknown"}


CLAIM_HINTS = re.compile(
    r"\b(require|requires|must|should|needs?|only|always|never|protected|auth(enticat)?|validat|return|calls?|endpoint|route|login|token|session|rate.?limit|cache|retry|timeout|public|private)\b",
    re.IGNORECASE,
)

CLAIM_EXTRACT_SYSTEM = """You read KT transcripts and documentation and
pull out assertion-shaped CLAIMS about how the system behaves.

A good claim is a specific, falsifiable statement about system behaviour,
architecture, data, or an operational contract. Reject small talk,
greetings, future plans and hedged speculation.

Return a strict JSON array of objects:
  [{"text": "...", "topic": "..."}]
`topic` is 2-5 words naming the subject (e.g. "auth on get endpoints",
"stripe retry policy", "duplicate orders bug").
Return ONLY the JSON array."""


def _llm_extract_claims(chunks: list[dict], max_claims: int) -> list[dict] | None:
    """LLM-based claim extraction. Falls back to None on failure or when
    no API key is configured — caller then uses regex extraction."""
    if nebius_client.demo_mode():
        return None
    joined = "\n\n".join(
        f"[{i+1}] {c['filename']} lines {c['start_line']}-{c['end_line']} ({c['kind']}):\n{c['text']}"
        for i, c in enumerate(chunks[:12])
    )
    user = (
        f"CHUNKS:\n{joined}\n\n"
        f"Extract up to {max_claims} distinct, assertion-shaped claims. Return the JSON array."
    )
    try:
        raw = nebius_client.chat(
            [{"role": "system", "content": CLAIM_EXTRACT_SYSTEM}, {"role": "user", "content": user}],
            temperature=0.1,
            max_tokens=1200,
        )
    except Exception:
        return None
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        return None
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None

    out: list[dict] = []
    for it in items[:max_claims]:
        text = (it.get("text") or "").strip()
        if len(text) < 15 or len(text) > 500:
            continue
        # Locate the chunk this claim came from (best-match by substring overlap)
        best = max(
            chunks,
            key=lambda c: _overlap(text, c["text"]),
            default=None,
        )
        if not best or _overlap(text, best["text"]) < 0.25:
            continue
        out.append({
            "text": text,
            "topic": (it.get("topic") or "").strip(),
            "filename": best["filename"],
            "kind": best["kind"],
            "start_line": best["start_line"],
            "end_line": best["end_line"],
            "chunk_id": best["id"],
        })
    return out or None


def _overlap(a: str, b: str) -> float:
    """Jaccard overlap between word sets of two strings."""
    aw = set(re.findall(r"\w+", a.lower()))
    bw = set(re.findall(r"\w+", b.lower()))
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / len(aw | bw)


def _excerpt_is_present(excerpt: str, source_text: str) -> bool:
    """True if `excerpt` is substantially present in `source_text`.

    Short quotes (<=20 non-whitespace chars) are accepted on exact
    whitespace-insensitive match. Longer quotes also pass if any 20-char
    run from them appears verbatim in the source — catches paraphrased or
    hallucinated code quotes while tolerating formatting differences.
    """
    clean = re.sub(r"\s+", "", excerpt)
    src_clean = re.sub(r"\s+", "", source_text)
    if not clean:
        return False
    if clean in src_clean:
        return True
    if len(clean) <= 20:
        return False  # short and not an exact substring → treat as hallucinated
    for i in range(0, len(clean) - 20, 10):
        if clean[i : i + 20] in src_clean:
            return True
    return False


def _regex_candidate_claims(project_id: int, max_claims: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT c.id, c.text, c.start_line, c.end_line, c.kind, s.filename "
            "FROM chunks c JOIN sources s ON s.id = c.source_id "
            "WHERE c.project_id = ? AND c.kind IN ('transcript', 'doc')",
            [project_id],
        ).fetchall()

    claims: list[dict] = []
    for row in rows:
        # Split on sentence boundaries + paragraph breaks only. A single
        # newline is a wrap, not a sentence end — joining those back keeps
        # claims like "every endpoint … requires\nauthentication" intact.
        joined = re.sub(r"(?<![.!?])\n(?!\n)", " ", row["text"])
        sentences = re.split(r"(?<=[.!?])\s+|\n\n+", joined)
        for sent in sentences:
            s = sent.strip()
            if len(s) < 20 or len(s) > 400:
                continue
            if not CLAIM_HINTS.search(s):
                continue
            claims.append({
                "text": s, "filename": row["filename"], "kind": row["kind"],
                "start_line": row["start_line"], "end_line": row["end_line"],
                "chunk_id": row["id"],
            })

    seen: set[str] = set()
    unique = []
    for c in claims:
        key = re.sub(r"\s+", " ", c["text"].lower())[:120]
        if key in seen:
            continue
        seen.add(key)
        unique.append(c)
    return unique[:max_claims]


def _candidate_claims(project_id: int, max_claims: int = 12) -> list[dict]:
    """LLM-based extraction with a regex fallback. Both produce the same shape."""
    with connect() as conn:
        chunks = conn.execute(
            "SELECT c.id, c.text, c.start_line, c.end_line, c.kind, s.filename "
            "FROM chunks c JOIN sources s ON s.id = c.source_id "
            "WHERE c.project_id = ? AND c.kind IN ('transcript', 'doc')",
            [project_id],
        ).fetchall()
    if not chunks:
        _LAST_METHOD["method"] = "none"
        return []
    llm_claims = _llm_extract_claims(chunks, max_claims)
    if llm_claims:
        _LAST_METHOD["method"] = "llm"
        return llm_claims
    log.info("gap_detector: LLM extraction unavailable or empty; falling back to regex")
    _LAST_METHOD["method"] = "regex"
    return _regex_candidate_claims(project_id, max_claims)


def last_extraction_method() -> str:
    return _LAST_METHOD["method"]


SYSTEM_PROMPT = """You are the KT Gap Detector in KT Intelligence.
You compare a single CLAIM taken from a KT transcript or document against
retrieved CODE EVIDENCE. Decide whether the code supports, contradicts, or
cannot verify the claim.

Hard rules:
- Only cite file paths, line numbers, and snippets that appear verbatim in
  the evidence provided. Never invent them.
- If the evidence is insufficient, say so and classify as "unverified".
- A mismatch between transcript and code is not automatic proof the code is
  wrong. Describe the discrepancy; propose a question for a human.
- Keep severity realistic: "high" only when there is a plausible security,
  data-loss, or operational impact.

Return a strict JSON object with these keys:
  category: one of "contradiction", "missing", "outdated", "unverified", "supported"
  severity: one of "low", "medium", "high"
  title: short string
  explanation: 1-3 sentences, grounded in the evidence
  code_evidence: array of {filename, start_line, end_line, excerpt}
  suggested_question: a single clarification question for the project owner
  confidence: number between 0 and 1
Return ONLY the JSON object, no prose."""


def _llm_classify(claim: dict, hits: list[Hit]) -> dict[str, Any] | None:
    evidence_block = format_evidence_block(hits) if hits else "[no code evidence retrieved]"
    user = (
        f"CLAIM (from {claim['filename']} lines "
        f"{claim['start_line']}-{claim['end_line']}, kind={claim['kind']}):\n"
        f"\"{claim['text']}\"\n\n"
        f"CODE EVIDENCE:\n{evidence_block}\n\n"
        "Return the JSON object now."
    )
    raw = nebius_client.chat(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        temperature=0.1,
        max_tokens=700,
    )
    # Tolerate ```json fences or trailing commentary
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def analyze_project(project_id: int) -> dict:
    """Run gap detection end-to-end.

    When a Nebius key is configured this calls the model; without one, it
    returns clearly-tagged demo findings so the rest of the UX stays usable.
    """
    claims = _candidate_claims(project_id)
    if not claims:
        return {"findings": [], "claims_examined": 0, "note": "No candidate claims found. Upload a transcript or doc that describes system behaviour."}

    if nebius_client.demo_mode():
        return _analyze_demo(project_id, claims)

    created = []
    for claim in claims:
        hits = search(project_id, claim["text"], k=4, kinds=["code"])
        result = _llm_classify(claim, hits)
        if not result:
            continue
        if result.get("category") == "supported":
            # Still worth remembering, but not reported as a gap.
            continue
        kt_evidence = {
            "filename": claim["filename"],
            "start_line": claim["start_line"],
            "end_line": claim["end_line"],
            "excerpt": claim["text"],
        }
        code_evidence = result.get("code_evidence") or []
        # Keep only evidence that references files we actually retrieved,
        # AND whose excerpt text is substantially present in a retrieved chunk.
        allowed = {h.filename: h.text for h in hits}
        verified_evidence = []
        for e in code_evidence:
            fn = e.get("filename")
            if fn not in allowed:
                continue
            excerpt = (e.get("excerpt") or "").strip()
            if excerpt and not _excerpt_is_present(excerpt, allowed[fn]):
                # Model invented or paraphrased lines not actually in the file.
                continue
            verified_evidence.append(e)
        code_evidence = verified_evidence or [h.as_dict() for h in hits[:2]]

        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO findings(project_id, category, severity, title, explanation, "
                "kt_evidence_json, code_evidence_json, suggested_question, confidence, status, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)",
                (
                    project_id,
                    result.get("category", "unverified"),
                    result.get("severity", "medium"),
                    (result.get("title") or claim["text"])[:200],
                    result.get("explanation", ""),
                    dumps(kt_evidence),
                    dumps(code_evidence),
                    result.get("suggested_question", ""),
                    float(result.get("confidence", 0.5)),
                    now_iso(),
                    now_iso(),
                ),
            )
            created.append(cur.lastrowid)
    _maybe_notify(project_id, len(created))
    return {
        "findings_created": len(created),
        "claims_examined": len(claims),
        "extraction_method": last_extraction_method(),
    }


def _maybe_notify(project_id: int, created_count: int) -> None:
    if not notifications.enabled() or created_count == 0:
        return
    with connect() as conn:
        proj = conn.execute("SELECT name FROM projects WHERE id = ?", [project_id]).fetchone()
        high = conn.execute(
            "SELECT COUNT(*) AS c FROM findings WHERE project_id = ? AND severity = 'high' AND status = 'open'",
            [project_id],
        ).fetchone()
    try:
        notifications.analysis_summary(project_id, proj["name"], created_count, high["c"] if high else 0)
    except Exception:
        pass


def _analyze_demo(project_id: int, claims: list[dict]) -> dict:
    """Seed demo findings tagged clearly as not a live-model result."""
    _LAST_METHOD["method"] = "regex-demo"
    created: list[int] = []
    for item in demo_data.gap_findings_for(claims):
        if item.get("category") == "supported":
            continue
        kt = next(
            (c for c in claims if any(k in c["text"].lower() for k in item["title"].lower().split()[:4])),
            claims[0],
        )
        kt_evidence = {
            "filename": kt["filename"], "start_line": kt["start_line"],
            "end_line": kt["end_line"], "excerpt": kt["text"],
        }
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO findings(project_id, category, severity, title, explanation, "
                "kt_evidence_json, code_evidence_json, suggested_question, confidence, status, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)",
                (
                    project_id, item["category"], item["severity"],
                    "[DEMO] " + item["title"], item["explanation"],
                    dumps(kt_evidence), dumps(item["code_evidence"]),
                    item["suggested_question"], item["confidence"],
                    now_iso(), now_iso(),
                ),
            )
            created.append(cur.lastrowid)
    return {
        "findings_created": len(created),
        "claims_examined": len(claims),
        "extraction_method": last_extraction_method(),
        "demo": True,
        "note": "Demo mode: findings are illustrative, not live model output. Set LLM_API_KEY in backend/.env for real analysis.",
    }


def list_findings(project_id: int, status: str | None = None, severity: str | None = None) -> list[dict]:
    sql = "SELECT * FROM findings WHERE project_id = ?"
    params: list[Any] = [project_id]
    if status:
        sql += " AND status = ?"
        params.append(status)
    if severity:
        sql += " AND severity = ?"
        params.append(severity)
    sql += " ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, created_at DESC"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    for r in rows:
        r["kt_evidence"] = json.loads(r.pop("kt_evidence_json") or "null")
        r["code_evidence"] = json.loads(r.pop("code_evidence_json") or "null")
    return rows


def update_finding_status(finding_id: int, status: str) -> dict | None:
    if status not in {"open", "resolved", "dismissed", "awaiting"}:
        raise ValueError("invalid status")
    with connect() as conn:
        conn.execute(
            "UPDATE findings SET status = ?, updated_at = ? WHERE id = ?",
            (status, now_iso(), finding_id),
        )
        row = conn.execute("SELECT * FROM findings WHERE id = ?", [finding_id]).fetchone()
    if not row:
        return None
    row["kt_evidence"] = json.loads(row.pop("kt_evidence_json") or "null")
    row["code_evidence"] = json.loads(row.pop("code_evidence_json") or "null")
    return row
