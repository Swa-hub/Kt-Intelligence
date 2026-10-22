"""Canned responses used when LLM_API_KEY is not set.

Every record returned from here is tagged `demo: true` and the frontend
displays an unmissable banner. Nothing in this module is presented as a
live model response.
"""


def gap_findings_for(claims: list[dict]) -> list[dict]:
    """Pick a convincing finding anchored to real retrieved claims."""
    out = []
    for c in claims:
        text = c["text"].lower()
        if "every endpoint" in text and "auth" in text:
            out.append({
                "category": "contradiction",
                "severity": "high",
                "title": "Transcript claims every endpoint requires auth, but GET /api/orders/<id> is not decorated",
                "explanation": (
                    "The transcript asserts that every endpoint on the orders-api is protected "
                    "by Bearer-token auth, enforced via @require_auth. The route handler "
                    "get_order in routes.py has no @require_auth decorator and no inline token "
                    "check — only @rate_limit. If this service is ever reachable from outside "
                    "the mobile app's trusted path, order details could be read without "
                    "authentication."
                ),
                "code_evidence": [{
                    "filename": "routes.py", "start_line": 33, "end_line": 50,
                    "excerpt": "@bp.get(\"/orders/<int:order_id>\")\n@rate_limit\ndef get_order(order_id: int):\n    ...",
                }],
                "suggested_question": "Was the missing @require_auth on get_order intentional (for the mobile app's unauthenticated prefetch) or an oversight?",
                "confidence": 0.82,
            })
            break
    # Second finding — payments retry claim
    for c in claims:
        text = c["text"].lower()
        if "retry" in text and ("3" in text or "three" in text):
            out.append({
                "category": "supported",
                "severity": "low",
                "title": "Retry count claim matches payments.charge implementation",
                "explanation": "Transcript says Stripe charges retry up to 3 times with exponential backoff. payments.charge() uses max_attempts=3 and doubles the delay each attempt.",
                "code_evidence": [{
                    "filename": "payments.py", "start_line": 14, "end_line": 31,
                    "excerpt": "def charge(order_id, amount_cents, token, max_attempts=3): ...",
                }],
                "suggested_question": "",
                "confidence": 0.88,
            })
            break
    # Third finding — idempotency open issue
    out.append({
        "category": "missing",
        "severity": "medium",
        "title": "Idempotency key handling is mentioned but never implemented",
        "explanation": (
            "The transcript (and ORDR-412) describe duplicate orders arising from mobile "
            "retries without an idempotency key. routes.py::create_order accepts no such "
            "header and the schema has no uniqueness constraint matching it. The gap "
            "between known problem and present code is itself the finding."
        ),
        "code_evidence": [{
            "filename": "routes.py", "start_line": 52, "end_line": 62,
            "excerpt": "@bp.post(\"/orders\")\n@require_auth\n@rate_limit\ndef create_order():\n    payload = request.get_json()\n    ...",
        }],
        "suggested_question": "Who owns ORDR-412, and is the fix on the mobile side, the backend side, or both?",
        "confidence": 0.74,
    })
    return out


def overview() -> dict:
    return {
        "purpose": "orders-api is a small Flask service that manages customer orders — listing, fetching, creating, and admin-cancelling them — backed by Postgres and integrated with Stripe for charges.",
        "stack": ["Python", "Flask", "Postgres", "Stripe", "Fly.io"],
        "entry_points": [
            {"filename": "routes.py", "note": "HTTP routes under /api/orders"},
        ],
        "modules": [
            {"name": "Routes", "purpose": "Four HTTP endpoints for orders.", "files": ["routes.py"], "notes": "Auth enforcement is inconsistent — get_order is missing @require_auth."},
            {"name": "Payments", "purpose": "Stripe charge with retry+backoff.", "files": ["payments.py"], "notes": "max_attempts=3 with doubling delay."},
            {"name": "Known issues", "purpose": "Open bug reports to resolve before handover.", "files": ["ORDR-412.md"], "notes": "Duplicate orders under mobile retry."},
        ],
        "open_questions": [
            "Is the missing @require_auth on get_order intentional?",
            "Who owns ORDR-412 (idempotency) and what's the target fix date?",
            "Which internal services call orders-api without going through the mobile app?",
        ],
        "demo": True,
    }


def chat_answer(question: str) -> dict:
    q = question.lower()
    if "login" in q or "auth" in q or "protected" in q:
        content = (
            "Three endpoints apply @require_auth in routes.py: /api/orders [1], "
            "POST /api/orders, and the admin cancel route. GET /api/orders/<id> [2] "
            "is not decorated — only @rate_limit is applied. The transcript claims "
            "the whole service is behind auth; the code disagrees for this one route. "
            "Likely either the mobile-app's always-signed-in prefetch is being relied "
            "on, or the decorator was dropped during a refactor."
        )
    elif "retry" in q or "payment" in q or "stripe" in q:
        content = (
            "payments.charge() [1] implements the retry the transcript describes: "
            "up to max_attempts=3, with a 1s → 2s → 4s exponential backoff. Only "
            "APIConnectionError triggers a retry; other Stripe errors propagate."
        )
    elif "file" in q or "start" in q or "first" in q:
        content = (
            "Start with routes.py [1] — it defines the four HTTP endpoints and shows "
            "how authentication, rate limiting, and role checks are composed. Then "
            "payments.py [2] for the Stripe integration. ORDR-412.md [3] documents a "
            "known bug worth understanding before touching create_order."
        )
    elif "kt" in q and ("miss" in q or "fail" in q):
        content = (
            "The KT session did not cover: (a) why GET /api/orders/<id> is missing "
            "@require_auth, (b) the exact fix plan for ORDR-412, (c) which services "
            "besides the mobile app call this API, (d) how role claims are populated "
            "in the JWT. These are good follow-ups to raise with the outgoing lead."
        )
    else:
        content = (
            "The uploaded sources describe the orders-api service: four HTTP routes "
            "in routes.py [1], Stripe charges with retry in payments.py [2], and a "
            "known duplicate-orders bug (ORDR-412) [3]. For a more targeted answer "
            "try asking about authentication, order creation, or the retry policy."
        )
    citations = [
        {"filename": "routes.py", "kind": "code", "start_line": 25, "end_line": 50, "chunk_id": 1, "source_id": 2, "text": "see routes.py"},
        {"filename": "payments.py", "kind": "code", "start_line": 14, "end_line": 31, "chunk_id": 2, "source_id": 3, "text": "see payments.py"},
        {"filename": "ORDR-412.md", "kind": "doc", "start_line": 1, "end_line": 20, "chunk_id": 3, "source_id": 4, "text": "see ORDR-412"},
    ]
    return {"answer": "⚑ DEMO MODE — this is a canned response, not a live model call.\n\n" + content, "citations": citations, "level": "demo", "demo": True}


def quiz(topic: str) -> dict:
    return {
        "demo": True,
        "questions": [
            {
                "question": "Which endpoint in routes.py is missing the @require_auth decorator?",
                "options": ["GET /api/orders", "GET /api/orders/<id>", "POST /api/orders", "POST /api/orders/<id>/cancel"],
                "correct_index": 1,
                "explanation": "Only get_order is undecorated; the other three carry @require_auth.",
                "evidence_refs": [{"filename": "routes.py", "start_line": 33, "end_line": 50}],
            },
            {
                "question": "How many times does payments.charge retry a failed Stripe call by default?",
                "options": ["1", "2", "3", "unbounded"],
                "correct_index": 2,
                "explanation": "max_attempts defaults to 3; delay doubles between attempts.",
                "evidence_refs": [{"filename": "payments.py", "start_line": 14, "end_line": 31}],
            },
            {
                "question": "Which bug does ORDR-412 describe?",
                "options": ["Duplicate orders under retry", "Stripe timeout bug", "Admin cancel role bypass", "SQL injection in list_orders"],
                "correct_index": 0,
                "explanation": "ORDR-412 covers duplicate rows from mobile retries without an idempotency key.",
                "evidence_refs": [{"filename": "ORDR-412.md", "start_line": 1, "end_line": 20}],
            },
        ],
    }
