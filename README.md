# KT Intelligence

![tests](https://img.shields.io/badge/tests-22%20passing-34483D)
![license](https://img.shields.io/badge/license-MIT-A7A39B)
![python](https://img.shields.io/badge/python-3.12-A7A39B)
![model](https://img.shields.io/badge/LLM-Groq%20%7C%20Nebius-B39A70)

> From knowledge transfer to verified working knowledge.

KT Intelligence turns scattered KT material — meeting transcripts, docs,
tickets, source code — into a verified, searchable, continuously
maintained knowledge base. It compares what people *said* against what
the code actually *implements*, surfaces real gaps with evidence on
both sides, teaches new joiners at their pace, and preserves confirmed
knowledge so the next handover is never from scratch.

The backend talks to any **OpenAI-compatible** LLM endpoint. The
default profile is **Groq** (free, fast, no credit card). The hackathon
profile swaps three env vars to **Nebius Token Factory** on an NVIDIA
Nemotron model — see "Switching to Nebius" below.

---

## What's in the box

| Module | What it does |
|---|---|
| **KT-to-Working-Knowledge** | Parses transcripts, docs, and code with full provenance (file, line range, kind). Chunking is code-aware. |
| **Gap & Contradiction Detector** | Extracts claims from KT material, retrieves candidate code evidence via BM25, and asks the model to classify each claim as contradiction / missing / outdated / unverified / supported — citing only evidence actually retrieved. |
| **Personal KT Tutor** | Grounded Q&A with inline `[n]` citations and a Beginner / Intermediate / Advanced level selector. Browser `speechSynthesis` for spoken explanations. Includes a **Quiz mode**. |
| **Project Overview** | On-demand, module-by-module summary generated from retrieved evidence. Invented filenames are stripped before display. |
| **Persistent Project Memory** | SQLite-backed. New content never silently overwrites older verified records — prior records flip to `conflicting` or `outdated` so a human can resolve. |

### Trust rules baked in

- **API key is backend-only.** The browser never sees it.
- **Model never invents citations.** Findings are filtered to only
  reference files that BM25 actually retrieved.
- **No silent memory overwrites.** Prior records become `conflicting`
  or `outdated`.
- **Uploads are data, never executed.** Filenames sanitised, size capped.
- **Missing API key opens demo mode** with every response clearly
  flagged — no fake "AI" claims.

## Quick start (Windows, no Docker)

### 1. Get a Groq API key

- Sign up at https://console.groq.com (Google or GitHub login, no card)
- API Keys → **Create API Key**, copy it (starts with `gsk_…`)

### 2. Configure

```cmd
cd backend
copy .env.example .env
notepad .env
```

Paste your key into the `LLM_API_KEY=` line. Save and close.

### 3. Backend

```cmd
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8010
```

Verify at http://localhost:8010/api/health — expect `"llm_configured": true`.

### 4. Frontend (second terminal)

```cmd
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The yellow "demo mode" banner should be
gone; the sidebar should show a green dot and "LLM connected".

### 5. Walk through the demo scenario

- Create a workspace from the landing page.
- Ingest page → drop these three files from `samples/demo-project/`:
  `transcript.txt`, `routes.py`, `payments.py` (plus `ORDR-412.md` if
  you want the bug report).
- Click **Run analysis**.
- Open **Gap Analysis** — expect a finding about the auth decorator
  being missing on `GET /api/orders/<id>`.
- **Send to memory** on that finding, then open **Project Memory**.
- **AI Tutor** → ask "Which endpoints are protected?" and watch the
  answer cite `routes.py` with line ranges.

## macOS / Linux

Same, but swap the activation step:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then edit .env and paste your key
uvicorn app.main:app --reload --port 8010
```

## Docker

```bash
cp backend/.env.example backend/.env   # paste key
docker compose up --build
# frontend: http://localhost:8080
```

## Switching to Nebius Token Factory

If you're submitting to the **Nebius × NVIDIA Global AI Hackathon**,
set these three lines in `backend/.env` instead of the Groq values:

```
LLM_BASE_URL=https://api.studio.nebius.com/v1/
LLM_API_KEY=<your Nebius Studio key>
LLM_MODEL=nvidia/Llama-3_1-Nemotron-70B-Instruct-HF
LLM_EMBED_MODEL=BAAI/bge-en-icl
```

Verify the exact model id in your Nebius account's catalogue before
committing to it — catalogues shift.

## Architecture

```
frontend/   React + Vite + Tailwind, dark theme
backend/    FastAPI + SQLite + BM25
            app/
              nebius_client.py   # single LLM call site (OpenAI-compatible)
              ingestion.py       # parse txt/md/pdf/docx/code → chunks
              retrieval.py       # BM25 over stored chunks
              gap_detector.py    # claim extraction → retrieval → classify
              tutor.py           # grounded Q&A, chat history
              overview.py        # module-by-module project summary
              quiz.py            # evidence-grounded quiz questions
              memory.py          # persistent records with conflict preservation
              demo_data.py       # canned responses when API key is missing
              main.py            # FastAPI routes
samples/demo-project/   KT transcript + code with a planted auth-gap
```

## Security

- **Bearer-token auth** — set `API_AUTH_TOKEN` in `backend/.env` to a long random string (`python -c "import secrets; print(secrets.token_urlsafe(32))"`). Every `/api/*` request except `/api/health` and the HMAC-verified webhook then requires `Authorization: Bearer <token>`. The frontend prompts for it in Settings and stores it in `localStorage` only.
- **Response hardening headers** — CSP (`default-src 'none'; frame-ancestors 'none'`), X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, HSTS. On by default; `SECURITY_HEADERS_ENABLED=false` to disable.
- **Rate limiting** — slowapi, applied per client IP. `RATE_LIMIT_LLM=20/minute` on the four expensive endpoints (`/analyze`, `/chat`, `/overview`, `/quiz`); `RATE_LIMIT_DEFAULT=120/minute` on everything else.
- **CORS** — explicit origin allowlist. Set `CORS_ORIGINS` to your frontend URL exactly in production; the default localhost origins must not ship to a public deploy.
- **GitHub webhook signature verification** — HMAC-SHA-256 via `GITHUB_WEBHOOK_SECRET`. Set it in production; an empty secret accepts unsigned payloads (dev convenience).
- **Trust discipline inside the LLM pipeline** — model citations are filtered to files actually retrieved; quoted code excerpts are verified against the real file; memory records never silently overwrite earlier verified knowledge.
- **Uploads** — size-capped (`MAX_UPLOAD_MB=25`), filenames path-sanitised, parsed as data (never executed). Audio files route through the configured transcription endpoint, not local execution.
- **SQL** — all queries parameterised; no string-building against user input.
- **Secrets handling** — `.env` is gitignored, `.env.example` carries only placeholders, API keys stay in backend process memory and are never sent to the browser.
- **XSS** — React auto-escapes rendered strings; no `dangerouslySetInnerHTML` anywhere in the frontend.
- **Audit** — `python -m scripts.security_audit` runs the local check (env not tracked, no secrets in source, CORS not wild, API auth set when origin isn't localhost, `pip-audit` for CVEs when installed).

## Scope and roadmap

**What's in the box**

- Hybrid retrieval: BM25 by default, upgraded to BM25 + semantic
  cosine blend when `LLM_EMBED_MODEL` is set (any OpenAI-compatible
  embeddings endpoint). Embeddings are computed and cached on first
  search per project.
- LLM-based claim extraction with a keyword fallback. The gap detector
  does not rely on fragile regex when the model is available.
- Code-quote verification: findings whose quoted excerpts don't
  actually appear in the retrieved file are dropped before display, so
  hallucinated line references never reach the UI.
- Normalised-topic conflict detection with a tech-synonym fold
  (auth ↔ authentication, retry ↔ retries, …), so the "no silent
  overwrites" guarantee works across differently-worded topic names.
- Change detection via SHA-256 hashing, auto-flagging of memory records
  whose source files change (both for direct re-upload and for pushes
  received via the GitHub webhook).
- A pytest suite (`backend/tests/`) covering ingestion, retrieval,
  memory lifecycle, gap-detector verification, and GitHub URL parsing.
- One-click Render deploy via `render.yaml` (backend + frontend as a
  Blueprint).
- Settings panel includes a step-by-step "connect this project to a
  GitHub repository" guide with the exact webhook URL, GitHub Action
  template path, and secret names pre-filled for the current project id.
- Lightweight learner model shown in the Tutor header — questions
  asked, files covered — so the learner can see what they've touched.

**Deliberate roadmap items**

- Code understanding is regex-based (top-level `def`/`class`/`function`
  boundaries with a line-based fallback). Tree-sitter would give fuller
  AST awareness and is on the roadmap, not shipping today.
- Repo import caps at 150 files per import. Monorepos need chunked
  import plus pagination.
- Single-user — there's no auth layer on the backend. Deploy behind a
  reverse proxy or add a middleware if that matters to you.
- The Tutor doesn't persist a per-learner model across projects.
- PDF/DOCX extraction is best-effort via `pypdf` and `python-docx`.

## License

MIT. See `LICENSE`.
