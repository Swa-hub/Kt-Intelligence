"""Tests for the bearer-token auth middleware and response headers."""
import importlib

import pytest
from fastapi.testclient import TestClient


def _reload_app():
    from app import config as _cfg, security as _sec, main as _main
    importlib.reload(_cfg)
    importlib.reload(_sec)
    importlib.reload(_main)
    return _main.app


def test_security_headers_present_by_default():
    app = _reload_app()
    c = TestClient(app)
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "no-referrer"
    assert "max-age" in r.headers.get("Strict-Transport-Security", "")
    assert "frame-ancestors 'none'" in r.headers.get("Content-Security-Policy", "")


def test_open_mode_without_token(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "")
    app = _reload_app()
    c = TestClient(app)
    r = c.get("/api/projects")
    assert r.status_code == 200  # no auth required when token unset


def test_rejects_requests_without_token(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "topsecret")
    app = _reload_app()
    c = TestClient(app)
    r = c.get("/api/projects")
    assert r.status_code == 401
    assert "Unauthorized" in r.json().get("error", "")


def test_accepts_requests_with_correct_token(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "topsecret")
    app = _reload_app()
    c = TestClient(app)
    r = c.get("/api/projects", headers={"Authorization": "Bearer topsecret"})
    assert r.status_code == 200


def test_wrong_token_rejected(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "topsecret")
    app = _reload_app()
    c = TestClient(app)
    r = c.get("/api/projects", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


def test_health_remains_public_even_with_auth(monkeypatch):
    monkeypatch.setenv("API_AUTH_TOKEN", "topsecret")
    app = _reload_app()
    c = TestClient(app)
    r = c.get("/api/health")
    assert r.status_code == 200
