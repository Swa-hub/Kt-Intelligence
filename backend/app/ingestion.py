"""Parse uploaded sources into chunks with provenance.

Uploads are treated as data, never executed. Each chunk carries source id,
line range, and kind so later evidence can be cited precisely.
"""
from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path

from . import change_detection
from .db import connect, dumps, now_iso

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rb",
    ".rs", ".cpp", ".c", ".cs", ".kt", ".swift", ".php", ".sql",
}
DOC_EXTENSIONS = {".md", ".rst", ".txt"}
TRANSCRIPT_EXTENSIONS = {".txt", ".vtt", ".srt"}


@dataclass
class Chunk:
    text: str
    start_line: int
    end_line: int
    kind: str
    meta: dict


def classify(filename: str, declared_kind: str | None = None) -> str:
    if declared_kind in {"transcript", "doc", "code", "ticket", "note"}:
        return declared_kind
    ext = Path(filename).suffix.lower()
    if ext in CODE_EXTENSIONS:
        return "code"
    if ext == ".pdf" or ext == ".docx":
        return "doc"
    name = filename.lower()
    if "transcript" in name or ext in {".vtt", ".srt"}:
        return "transcript"
    if ext in DOC_EXTENSIONS:
        return "doc"
    return "note"


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:
            return f"[Could not extract PDF text: {e}]"
    if ext == ".docx":
        try:
            import docx
            doc = docx.Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            return f"[Could not extract DOCX text: {e}]"
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1", errors="replace")


def _chunk_code(text: str, filename: str) -> list[Chunk]:
    """Split code by top-level defs/classes/functions, preserving line numbers."""
    lines = text.splitlines()
    if not lines:
        return []
    boundary_re = re.compile(
        r"^\s*(def |class |function |async def |export (default |function |class )|public |private |protected )"
    )
    boundaries = [i for i, ln in enumerate(lines) if boundary_re.match(ln)]
    if not boundaries or boundaries[0] != 0:
        boundaries = [0] + boundaries
    boundaries.append(len(lines))

    chunks: list[Chunk] = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        segment = "\n".join(lines[s:e]).strip()
        if not segment:
            continue
        # Hard cap to avoid giant blocks
        if e - s > 120:
            for sub_s in range(s, e, 80):
                sub_e = min(sub_s + 80, e)
                sub_text = "\n".join(lines[sub_s:sub_e]).strip()
                if sub_text:
                    chunks.append(Chunk(sub_text, sub_s + 1, sub_e, "code", {"file": filename}))
        else:
            chunks.append(Chunk(segment, s + 1, e, "code", {"file": filename}))
    return chunks


def _chunk_text(text: str, kind: str, filename: str) -> list[Chunk]:
    lines = text.splitlines()
    chunks: list[Chunk] = []
    window = 40
    stride = 32
    for start in range(0, max(len(lines), 1), stride):
        end = min(start + window, len(lines))
        segment = "\n".join(lines[start:end]).strip()
        if segment:
            chunks.append(Chunk(segment, start + 1, end, kind, {"file": filename}))
        if end >= len(lines):
            break
    return chunks


def chunk_file(text: str, kind: str, filename: str) -> list[Chunk]:
    if kind == "code":
        return _chunk_code(text, filename)
    return _chunk_text(text, kind, filename)


def save_source_and_chunks(
    project_id: int,
    filename: str,
    stored_path: Path,
    declared_kind: str | None,
    *,
    origin: str = "upload",
) -> dict:
    kind = classify(filename, declared_kind)
    data = stored_path.read_bytes()
    content_hash = change_detection.hash_bytes(data)
    prior = change_detection.previous_source(project_id, filename)

    # Idempotent re-upload: same filename + same bytes → skip and return existing.
    if prior and prior.get("content_hash") == content_hash:
        return {
            "source_id": prior["id"],
            "filename": filename,
            "kind": prior["kind"],
            "chunks": 0,
            "size_bytes": prior["size_bytes"],
            "unchanged": True,
        }

    text = extract_text(stored_path)
    chunks = chunk_file(text, kind, filename)
    created = now_iso()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO sources(project_id, kind, filename, stored_path, size_bytes, content_hash, origin, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, kind, filename, str(stored_path), stored_path.stat().st_size, content_hash, origin, created),
        )
        source_id = cur.lastrowid
        for ch in chunks:
            conn.execute(
                "INSERT INTO chunks(project_id, source_id, kind, text, start_line, end_line, meta_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (project_id, source_id, ch.kind, ch.text, ch.start_line, ch.end_line, dumps(ch.meta)),
            )

    result: dict = {
        "source_id": source_id,
        "filename": filename,
        "kind": kind,
        "chunks": len(chunks),
        "size_bytes": stored_path.stat().st_size,
    }
    # If this filename existed before, mark the old version superseded and
    # flag any memory records that cite it as conflicting for human review.
    if prior:
        change_detection.mark_superseded(prior["id"], source_id)
        affected = change_detection.flag_memory_for_file(project_id, filename)
        result["replaced_source_id"] = prior["id"]
        result["flagged_memory_ids"] = affected
    return result
