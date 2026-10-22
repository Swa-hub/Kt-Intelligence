"""Hybrid BM25 + semantic retrieval over stored chunks.

Keyword retrieval (BM25) runs with zero external calls and is always
available. When LLM_EMBED_MODEL is configured, chunks are embedded on
first search and cosine similarity is folded into the final score — the
blended ranking catches "@require_auth" ↔ "auth decorator" matches that
pure BM25 misses.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from . import nebius_client
from .config import settings
from .db import connect, dumps


_tokeniser = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")


def tokenise(text: str) -> list[str]:
    return [t.lower() for t in _tokeniser.findall(text)]


_COMMENT_LINE = re.compile(r"^\s*(#|//|\*)")
_DEFINITION = re.compile(r"\b(def |class |function |import |from |export |public |private |protected )")


def _code_density(text: str) -> float:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    code = sum(1 for ln in lines if not _COMMENT_LINE.match(ln))
    base = code / len(lines)
    if not _DEFINITION.search(text):
        base *= 0.3
    return base


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


@dataclass
class Hit:
    chunk_id: int
    source_id: int
    filename: str
    kind: str
    text: str
    start_line: int
    end_line: int
    score: float

    def as_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_id": self.source_id,
            "filename": self.filename,
            "kind": self.kind,
            "text": self.text,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "score": round(self.score, 3),
        }


def _load_chunks(project_id: int, kinds: list[str] | None = None) -> list[dict]:
    with connect() as conn:
        if kinds:
            placeholders = ",".join("?" for _ in kinds)
            rows = conn.execute(
                f"SELECT c.id, c.source_id, c.kind, c.text, c.start_line, c.end_line, "
                f"c.meta_json, c.embedding_json, s.filename FROM chunks c "
                f"JOIN sources s ON s.id = c.source_id "
                f"WHERE c.project_id = ? AND c.kind IN ({placeholders})",
                [project_id, *kinds],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT c.id, c.source_id, c.kind, c.text, c.start_line, c.end_line, "
                "c.meta_json, c.embedding_json, s.filename FROM chunks c "
                "JOIN sources s ON s.id = c.source_id "
                "WHERE c.project_id = ?",
                [project_id],
            ).fetchall()
    return rows


def _ensure_embeddings(rows: list[dict]) -> bool:
    """Compute and persist embeddings for any chunks missing them. Returns
    True if any embeddings are available afterwards."""
    if not settings.llm_embed_model:
        return False
    missing = [r for r in rows if not r.get("embedding_json")]
    if missing:
        texts = [r["text"] for r in missing]
        # Embed in batches of 64 to keep requests small.
        with connect() as conn:
            for i in range(0, len(missing), 64):
                batch = missing[i : i + 64]
                try:
                    vecs = nebius_client.embed([b["text"] for b in batch])
                except Exception:
                    return False
                if not vecs:
                    return False
                for row, vec in zip(batch, vecs):
                    conn.execute(
                        "UPDATE chunks SET embedding_json = ? WHERE id = ?",
                        [dumps(vec), row["id"]],
                    )
                    row["embedding_json"] = dumps(vec)
    return any(r.get("embedding_json") for r in rows)


def search(project_id: int, query: str, k: int = 6, kinds: list[str] | None = None) -> list[Hit]:
    rows = _load_chunks(project_id, kinds)
    if not rows:
        return []

    # BM25 scores (always)
    corpus = [tokenise(r["text"]) for r in rows]
    bm25 = BM25Okapi(corpus)
    bm_scores = bm25.get_scores(tokenise(query))

    # Normalise BM25 to [0, 1] so it combines cleanly with cosine
    max_bm = max(bm_scores) if len(bm_scores) and max(bm_scores) > 0 else 1.0
    norm_bm = [s / max_bm for s in bm_scores]

    # Semantic scores (when embeddings available)
    sem_scores: list[float] | None = None
    if _ensure_embeddings(rows):
        try:
            qvec = nebius_client.embed([query])
            if qvec:
                q = qvec[0]
                sem_scores = []
                for r in rows:
                    emb = json.loads(r["embedding_json"]) if r.get("embedding_json") else None
                    sem_scores.append(_cosine(q, emb) if emb else 0.0)
        except Exception:
            sem_scores = None

    adjusted: list[tuple[dict, float]] = []
    for i, r in enumerate(rows):
        s = norm_bm[i]
        if sem_scores is not None:
            # 60/40 semantic/keyword blend — adjust by evidence that the two concur
            s = 0.4 * norm_bm[i] + 0.6 * max(sem_scores[i], 0.0)
        if r["kind"] == "code":
            s = s * (0.5 + 0.5 * _code_density(r["text"]))
        adjusted.append((r, s))

    ranked = sorted(adjusted, key=lambda x: x[1], reverse=True)[:k]
    return [
        Hit(
            chunk_id=r["id"],
            source_id=r["source_id"],
            filename=r["filename"],
            kind=r["kind"],
            text=r["text"],
            start_line=r["start_line"] or 0,
            end_line=r["end_line"] or 0,
            score=float(s),
        )
        for r, s in ranked
        if s > 0
    ]


def format_evidence_block(hits: list[Hit]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(f"[{i}] {h.filename}:{h.start_line}-{h.end_line} ({h.kind})\n{h.text}")
    return "\n\n".join(parts)
