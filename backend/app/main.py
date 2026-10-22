from pathlib import Path

import json

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from . import (
    benchmark as benchmark_mod,
    drift as drift_mod,
    export as export_mod,
    gap_detector,
    github_import,
    memory as memory_mod,
    nebius_client,
    notifications,
    overview as overview_mod,
    quiz,
    security as security_mod,
    transcription,
    tutor,
    webhooks,
)
from .config import settings
from .db import connect, init_db, now_iso
from .ingestion import save_source_and_chunks

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default] if settings.rate_limit_default else [])
from .schemas import (
    ChatRequest,
    FindingStatusUpdate,
    GitHubImport,
    MemoryCreate,
    MemoryStatusUpdate,
    PrCommentRequest,
    ProjectCreate,
)

app = FastAPI(title="KT Intelligence API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Order matters — middleware runs outermost-first on the way in.
# CORS → security headers → bearer auth → routes.
app.add_middleware(security_mod.BearerAuthMiddleware)
app.add_middleware(security_mod.SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

LLM_RATE = settings.rate_limit_llm or "20/minute"


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.exception_handler(nebius_client.LLMError)
async def llm_error_handler(_request, exc: nebius_client.LLMError):
    status_code = 503 if isinstance(exc, nebius_client.LLMNotConfigured) else 502
    return JSONResponse(status_code=status_code, content={"error": str(exc)})


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_configured": nebius_client.is_configured(),
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "embed_model": settings.llm_embed_model or None,
    }


# ---------- Projects ----------

@app.post("/api/projects")
def create_project(body: ProjectCreate) -> dict:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects(name, description, created_at) VALUES (?, ?, ?)",
            (body.name, body.description, now_iso()),
        )
        pid = cur.lastrowid
        row = conn.execute("SELECT * FROM projects WHERE id = ?", [pid]).fetchone()
    return row


@app.get("/api/projects")
def list_projects() -> list[dict]:
    with connect() as conn:
        return conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()


@app.get("/api/projects/{project_id}")
def get_project(project_id: int) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", [project_id]).fetchone()
        if not row:
            raise HTTPException(404, "project not found")
        row["sources"] = conn.execute(
            "SELECT id, kind, filename, size_bytes, created_at FROM sources WHERE project_id = ? ORDER BY created_at DESC",
            [project_id],
        ).fetchall()
        counts = conn.execute(
            "SELECT "
            " (SELECT COUNT(*) FROM chunks WHERE project_id = ?) AS chunks,"
            " (SELECT COUNT(*) FROM findings WHERE project_id = ? AND status='open') AS open_findings,"
            " (SELECT COUNT(*) FROM findings WHERE project_id = ?) AS total_findings,"
            " (SELECT COUNT(*) FROM memory_records WHERE project_id = ?) AS memory_records",
            [project_id, project_id, project_id, project_id],
        ).fetchone()
        row["stats"] = counts
    return row


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int) -> dict:
    with connect() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", [project_id])
    return {"deleted": project_id}


# ---------- Uploads ----------

@app.post("/api/projects/{project_id}/upload")
async def upload(project_id: int, file: UploadFile = File(...), kind: str | None = Form(None)) -> dict:
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM projects WHERE id = ?", [project_id]).fetchone():
            raise HTTPException(404, "project not found")

    # Reject empty names and traversal attempts
    safe_name = Path(file.filename or "upload.bin").name
    if not safe_name:
        raise HTTPException(400, "invalid filename")

    target_dir = Path(settings.upload_dir) / f"project_{project_id}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_name

    max_bytes = settings.max_upload_mb * 1024 * 1024
    size = 0
    with target.open("wb") as out:
        while chunk := await file.read(1024 * 64):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                target.unlink(missing_ok=True)
                raise HTTPException(413, f"file exceeds {settings.max_upload_mb} MB")
            out.write(chunk)

    # If this is an audio/video file, transcribe it first and store the
    # transcript as the actual source.
    if transcription.is_audio(safe_name):
        try:
            text = transcription.transcribe(target)
        except nebius_client.LLMError:
            raise
        except Exception as e:
            raise HTTPException(500, f"transcription failed: {e}")
        transcript_name = Path(safe_name).stem + ".transcript.txt"
        transcript_path = target_dir / transcript_name
        transcript_path.write_text(text, encoding="utf-8")
        try:
            result = save_source_and_chunks(project_id, transcript_name, transcript_path, "transcript", origin="transcription")
            result["transcribed_from"] = safe_name
            return result
        except Exception as e:
            raise HTTPException(500, f"ingestion failed: {e}")

    try:
        result = save_source_and_chunks(project_id, safe_name, target, kind)
    except Exception as e:
        raise HTTPException(500, f"ingestion failed: {e}")
    return result


@app.post("/api/projects/{project_id}/import-github")
def import_github(project_id: int, body: GitHubImport) -> dict:
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM projects WHERE id = ?", [project_id]).fetchone():
            raise HTTPException(404, "project not found")
    try:
        return github_import.import_repo(project_id, body.url)
    except github_import.GitHubImportError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"import failed: {e}")


@app.get("/api/projects/{project_id}/export", response_class=PlainTextResponse)
def export_project(project_id: int) -> str:
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM projects WHERE id = ?", [project_id]).fetchone():
            raise HTTPException(404, "project not found")
    return export_mod.build_markdown(project_id)


@app.get("/api/projects/{project_id}/attention")
def attention(project_id: int) -> dict:
    with connect() as conn:
        if not conn.execute("SELECT 1 FROM projects WHERE id = ?", [project_id]).fetchone():
            raise HTTPException(404, "project not found")
    return drift_mod.attention_feed(project_id)


@app.get("/api/memory/{record_id}/events")
def memory_events(record_id: int) -> list[dict]:
    return memory_mod.events_for(record_id)


@app.post("/api/projects/{project_id}/pr-comment")
def pr_comment(project_id: int, body: PrCommentRequest) -> dict:
    with connect() as conn:
        proj = conn.execute("SELECT id, name FROM projects WHERE id = ?", [project_id]).fetchone()
        if not proj:
            raise HTTPException(404, "project not found")
    md = drift_mod.pr_comment_markdown(project_id, proj["name"], body.changed_files, settings.public_base_url or None)
    return {"markdown": md}


@app.post("/api/webhooks/github/{project_id}")
async def github_webhook(project_id: int, request: Request, x_hub_signature_256: str | None = Header(None), x_github_event: str | None = Header(None)) -> dict:
    body = await request.body()
    if not webhooks.verify_signature(body, x_hub_signature_256):
        raise HTTPException(401, "invalid signature")
    if x_github_event == "ping":
        return {"ok": True, "message": "pong"}
    if x_github_event != "push":
        return {"ok": True, "ignored": x_github_event}
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "invalid json")
    try:
        return webhooks.handle_push(project_id, payload)
    except webhooks.WebhookError as e:
        raise HTTPException(400, str(e))


@app.get("/api/benchmark")
def benchmark() -> dict:
    """Run the demo scenario end-to-end and return concrete metrics.
    Safe to call anytime — uses a disposable project."""
    return benchmark_mod.run(cleanup=True)


@app.patch("/api/findings/{finding_id}/assign")
def assign_finding(finding_id: int, body: dict) -> dict:
    owner = (body.get("owner") or "").strip() or None
    with connect() as conn:
        conn.execute("UPDATE findings SET owner = ?, updated_at = ? WHERE id = ?", (owner, now_iso(), finding_id))
        row = conn.execute("SELECT * FROM findings WHERE id = ?", [finding_id]).fetchone()
    if not row:
        raise HTTPException(404, "finding not found")
    return row


@app.patch("/api/findings/{finding_id}/snooze")
def snooze_finding(finding_id: int, body: dict) -> dict:
    until = (body.get("until") or "").strip() or None
    with connect() as conn:
        conn.execute("UPDATE findings SET snoozed_until = ?, updated_at = ? WHERE id = ?", (until, now_iso(), finding_id))
        row = conn.execute("SELECT * FROM findings WHERE id = ?", [finding_id]).fetchone()
    if not row:
        raise HTTPException(404, "finding not found")
    return row


@app.post("/api/projects/{project_id}/quiz/attempt")
def record_quiz_attempt(project_id: int, body: dict) -> dict:
    topic = (body.get("topic") or "").strip()
    question = (body.get("question") or "").strip()
    correct = 1 if body.get("correct") else 0
    if not topic or not question:
        raise HTTPException(400, "topic and question are required")
    with connect() as conn:
        conn.execute(
            "INSERT INTO quiz_attempts(project_id, topic, question, correct, created_at) VALUES (?, ?, ?, ?, ?)",
            [project_id, topic, question, correct, now_iso()],
        )
    return {"ok": True}


@app.get("/api/chunks/{chunk_id}")
def get_chunk(chunk_id: int) -> dict:
    """Return a chunk's full text for the inline citation viewer."""
    with connect() as conn:
        row = conn.execute(
            "SELECT c.id, c.text, c.start_line, c.end_line, c.kind, s.filename FROM chunks c "
            "JOIN sources s ON s.id = c.source_id WHERE c.id = ?",
            [chunk_id],
        ).fetchone()
    if not row:
        raise HTTPException(404, "chunk not found")
    return row


# ---------- Analysis ----------

@app.post("/api/projects/{project_id}/analyze")
@limiter.limit(LLM_RATE)
def analyze(project_id: int, request: Request) -> dict:
    return gap_detector.analyze_project(project_id)


@app.get("/api/projects/{project_id}/findings")
def findings(project_id: int, status: str | None = None, severity: str | None = None) -> list[dict]:
    return gap_detector.list_findings(project_id, status=status, severity=severity)


@app.patch("/api/findings/{finding_id}")
def update_finding(finding_id: int, body: FindingStatusUpdate) -> dict:
    row = gap_detector.update_finding_status(finding_id, body.status)
    if not row:
        raise HTTPException(404, "finding not found")
    return row


# ---------- Chat / Tutor ----------

@app.post("/api/projects/{project_id}/chat")
@limiter.limit(LLM_RATE)
def chat(project_id: int, body: ChatRequest, request: Request) -> dict:
    return tutor.answer(project_id, body.question, body.level)


@app.get("/api/projects/{project_id}/chat")
def chat_history(project_id: int) -> list[dict]:
    return tutor.history(project_id)


@app.get("/api/projects/{project_id}/learning")
def learning_progress(project_id: int) -> dict:
    return tutor.learning_progress(project_id)


@app.post("/api/projects/{project_id}/overview")
@limiter.limit(LLM_RATE)
def project_overview(project_id: int, request: Request) -> dict:
    return overview_mod.generate(project_id)


@app.post("/api/projects/{project_id}/quiz")
@limiter.limit(LLM_RATE)
def project_quiz(project_id: int, body: dict, request: Request) -> dict:
    topic = (body.get("topic") or "").strip()
    n = int(body.get("n") or 3)
    if not topic:
        raise HTTPException(400, "topic is required")
    return quiz.generate(project_id, topic, n=max(1, min(n, 8)))


# ---------- Memory ----------

@app.post("/api/projects/{project_id}/memory")
def create_memory(project_id: int, body: MemoryCreate) -> dict:
    return memory_mod.create_record(
        project_id,
        body.topic,
        body.content,
        body.verification_status,
        body.sources,
        body.confidence,
    )


@app.get("/api/projects/{project_id}/memory")
def list_memory(project_id: int, q: str | None = None, status: str | None = None) -> list[dict]:
    return memory_mod.list_records(project_id, query=q, status=status)


@app.patch("/api/memory/{record_id}")
def update_memory(record_id: int, body: MemoryStatusUpdate) -> dict:
    row = memory_mod.update_status(record_id, body.verification_status)
    if not row:
        raise HTTPException(404, "memory record not found")
    return row
