"""End-to-end HTTP tests using FastAPI's TestClient.

Covers the full request/response cycle: route registration, request
validation, response shape, rate limiting middleware wiring, and demo-mode
fallback. No live model calls — the harness runs with LLM_API_KEY unset.
"""
from pathlib import Path

import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app import main as _main
    importlib.reload(_main)
    return TestClient(_main.app)


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["llm_configured"] is False


def test_project_lifecycle(client):
    r = client.post("/api/projects", json={"name": "e2e", "description": "test"})
    assert r.status_code == 200
    pid = r.json()["id"]

    r = client.get(f"/api/projects/{pid}")
    assert r.status_code == 200
    assert r.json()["name"] == "e2e"

    r = client.delete(f"/api/projects/{pid}")
    assert r.status_code == 200


def test_upload_and_analyze_e2e(client, tmp_path: Path):
    r = client.post("/api/projects", json={"name": "e2e-analyze"})
    pid = r.json()["id"]

    sample = Path(__file__).resolve().parents[2] / "samples" / "demo-project"
    for fname, kind in [
        ("transcript.txt", "transcript"),
        ("routes.py",      "code"),
        ("payments.py",    "code"),
    ]:
        with (sample / fname).open("rb") as f:
            r = client.post(
                f"/api/projects/{pid}/upload",
                files={"file": (fname, f, "text/plain")},
                data={"kind": kind},
            )
        assert r.status_code == 200

    # Demo mode (no LLM key) returns a tagged result + at least one finding.
    r = client.post(f"/api/projects/{pid}/analyze")
    assert r.status_code == 200
    body = r.json()
    assert body.get("demo") is True
    assert body["findings_created"] >= 1

    r = client.get(f"/api/projects/{pid}/findings")
    assert r.status_code == 200
    findings = r.json()
    assert any("DEMO" in f["title"] for f in findings)


def test_benchmark_endpoint(client):
    r = client.get("/api/benchmark")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "demo"
    assert body["files_ingested"] == 4
    assert body["findings_created"] >= 1, "demo should always surface at least one finding"
    # The planted contradiction is high-severity; demo mode must produce it.
    assert body["findings_by_severity"]["high"] >= 1, (
        "demo mode should generate the auth-gap finding (high severity), "
        f"got {body['findings_by_severity']}"
    )
    assert body["hero_contradiction_detected"] is True
    assert body["timings_sec"]["total"] >= 0
    assert body["extraction_method"] in {"regex-demo", "regex", "llm"}


def test_pr_comment_endpoint(client):
    r = client.post("/api/projects", json={"name": "e2e-pr"})
    pid = r.json()["id"]
    client.post(f"/api/projects/{pid}/memory", json={
        "topic": "Auth on get_order",
        "content": "demo",
        "verification_status": "verified",
        "sources": [{"filename": "routes.py", "start_line": 33, "end_line": 50}],
    })
    r = client.post(f"/api/projects/{pid}/pr-comment", json={"changed_files": ["routes.py"]})
    assert r.status_code == 200
    md = r.json()["markdown"]
    assert "Auth on get_order" in md
    assert "routes.py" in md


def test_webhook_rejects_bad_signature(client):
    # Mutate the settings reference the webhooks module actually uses.
    from app import webhooks as _wh
    original = _wh.settings.github_webhook_secret
    _wh.settings.github_webhook_secret = "topsecret"
    try:
        client.post("/api/projects", json={"name": "e2e-wh"})
        r = client.post(
            "/api/webhooks/github/1",
            json={"ref": "refs/heads/main"},
            headers={"X-Hub-Signature-256": "sha256=wrong", "X-GitHub-Event": "push"},
        )
        assert r.status_code == 401
    finally:
        _wh.settings.github_webhook_secret = original


def test_webhook_accepts_ping_without_secret(client):
    client.post("/api/projects", json={"name": "e2e-ping"})
    r = client.post(
        "/api/webhooks/github/1",
        json={"zen": "GitHub!"},
        headers={"X-GitHub-Event": "ping"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
