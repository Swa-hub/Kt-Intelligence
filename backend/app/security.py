"""Security middleware: bearer-token auth + response hardening headers.

Design:
  * Auth is OFF by default (empty API_AUTH_TOKEN) so the demo flow still
    works at localhost. Setting the env var turns it on for every request
    with a short list of unauthenticated exceptions.
  * Public exceptions: /api/health (readiness probe), /api/webhooks/*
    (HMAC-verified separately), /docs and /openapi.json (optional).
  * Timing-safe comparison via hmac.compare_digest.
"""
from __future__ import annotations

import hmac

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from .config import settings


# Paths that stay reachable without a bearer token.
_PUBLIC_PREFIXES = (
    "/api/health",
    "/api/webhooks/",
)
_PUBLIC_EXACT = {"/", "/docs", "/openapi.json", "/redoc"}


def _is_public(path: str) -> bool:
    if path in _PUBLIC_EXACT:
        return True
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Enforce Authorization: Bearer <token> when API_AUTH_TOKEN is set."""

    async def dispatch(self, request: Request, call_next):
        token = settings.api_auth_token
        if not token or _is_public(request.url.path):
            return await call_next(request)
        if request.method == "OPTIONS":
            # CORS preflight — the browser handles auth after the preflight.
            return await call_next(request)

        header = request.headers.get("authorization", "")
        presented = header[7:] if header.lower().startswith("bearer ") else ""
        if not presented or not hmac.compare_digest(presented, token):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized. Set the Authorization: Bearer header."},
            )
        return await call_next(request)


# Content-Security-Policy allows the API to serve its own JSON and PlainText
# responses. The frontend bundle is served separately (static host or nginx
# container) with its own CSP; this policy covers the API container.
_CSP = (
    "default-src 'none'; "
    "frame-ancestors 'none'; "
    "base-uri 'none'; "
    "form-action 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Append conservative security headers to every API response."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if not settings.security_headers_enabled:
            return response
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        headers.setdefault("Content-Security-Policy", _CSP)
        # HSTS is only meaningful over HTTPS — safe to send regardless; browsers
        # ignore it on plain HTTP. Use a conservative 180-day window.
        headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains")
        return response
