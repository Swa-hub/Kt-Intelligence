"""Local security audit — opinionated, runs in seconds.

Checks:
  1. .env is not tracked by git (if this is a git working tree)
  2. .env.example doesn't carry a real-looking key
  3. API_AUTH_TOKEN is set when CORS allows a non-localhost origin
  4. CORS doesn't contain '*'
  5. SECURITY_HEADERS_ENABLED is on
  6. No obviously-pasted secrets anywhere in app/ and samples/
  7. pip-audit (if installed) reports no known CVEs in requirements

Exit code is non-zero on any critical finding. Non-critical issues
print a WARN line and still allow 0 on exit.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent  # backend/
PROJECT_ROOT = ROOT.parent


# Patterns that look like real secrets.
SECRET_PATTERNS = [
    (re.compile(r"\bgsk_[A-Za-z0-9]{40,}"), "Groq API key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}"), "OpenAI-style key"),
    (re.compile(r"\bghp_[A-Za-z0-9]{36,}"), "GitHub personal token"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}"), "AWS access key id"),
]


def c(label: str) -> str:
    return f"\x1b[1;36m{label}\x1b[0m"


def ok(msg: str) -> None:
    print(f"  \x1b[32m✓\x1b[0m {msg}")


def warn(msg: str) -> None:
    print(f"  \x1b[33m!\x1b[0m {msg}")


def fail(msg: str) -> None:
    print(f"  \x1b[31m✗\x1b[0m {msg}")


def run(cmd: list[str]) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return -1, str(e)


def check_env_not_tracked(critical: list) -> None:
    print(c("· .env not tracked by git"))
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        warn("Not a git working tree — skipping; verify manually when you push.")
        return
    rc, out = run(["git", "-C", str(PROJECT_ROOT), "ls-files", "backend/.env"])
    if rc == 0 and out.strip():
        fail("backend/.env IS tracked by git. Remove it and rotate every secret inside.")
        critical.append(".env tracked")
    else:
        ok("backend/.env is not tracked.")


def check_env_example_clean(critical: list) -> None:
    print(c("· .env.example contains no real secrets"))
    ex = ROOT / ".env.example"
    if not ex.exists():
        warn("No .env.example — nothing to check.")
        return
    text = ex.read_text(errors="ignore")
    for pat, name in SECRET_PATTERNS:
        if pat.search(text):
            fail(f"{name} pattern found in .env.example — delete it.")
            critical.append(f"secret in .env.example ({name})")
            return
    ok(".env.example is a placeholder.")


def check_runtime_config(critical: list) -> None:
    print(c("· Runtime config sanity"))
    from app.config import settings  # type: ignore
    cors = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    has_wildcard = any(o == "*" for o in cors)
    public_origin = any(not (o.startswith("http://localhost") or o.startswith("http://127.0.0.1")) for o in cors)

    if has_wildcard:
        fail("CORS_ORIGINS contains '*'. Set it to your exact frontend URL.")
        critical.append("CORS wildcard")
    else:
        ok("CORS_ORIGINS has no wildcard.")

    if public_origin and not settings.api_auth_token:
        fail("CORS allows a non-localhost origin but API_AUTH_TOKEN is empty. Set a bearer token.")
        critical.append("public CORS without auth")
    elif not settings.api_auth_token:
        warn("API_AUTH_TOKEN is empty (open mode). OK for localhost demos; required in production.")
    else:
        ok("API_AUTH_TOKEN is set.")

    if settings.security_headers_enabled:
        ok("SECURITY_HEADERS_ENABLED is on.")
    else:
        fail("SECURITY_HEADERS_ENABLED is off. Turn it on unless embedding elsewhere.")
        critical.append("security headers off")

    if not settings.github_webhook_secret:
        warn("GITHUB_WEBHOOK_SECRET is empty. OK for localhost testing; set it in production.")
    else:
        ok("GITHUB_WEBHOOK_SECRET is set.")


def check_source_for_secrets(critical: list) -> None:
    print(c("· No pasted secrets in source"))
    targets = [ROOT / "app", PROJECT_ROOT / "samples"]
    for d in targets:
        for p in d.rglob("*"):
            if not p.is_file() or p.suffix not in {".py", ".md", ".txt", ".yml", ".yaml", ".json"}:
                continue
            try:
                text = p.read_text(errors="ignore")
            except OSError:
                continue
            for pat, name in SECRET_PATTERNS:
                m = pat.search(text)
                if m:
                    fail(f"{name} in {p.relative_to(PROJECT_ROOT)}: {m.group(0)[:14]}…")
                    critical.append(f"secret in {p.name}")
    ok("No obvious secrets found in source.")


def check_pip_audit(critical: list) -> None:
    print(c("· pip-audit (optional)"))
    rc, out = run(["pip-audit", "--strict", "-r", str(ROOT / "requirements.txt")])
    if rc == -1 or "not found" in out.lower():
        warn("pip-audit not installed. Install it: `pip install pip-audit`.")
        return
    if rc != 0:
        fail("pip-audit reported vulnerabilities:")
        print("    " + "\n    ".join(out.splitlines()[:20]))
        critical.append("pip-audit CVEs")
    else:
        ok("No known CVEs in current dependencies.")


def main() -> int:
    print("KT Intelligence security audit")
    print("=" * 56)
    critical: list[str] = []
    check_env_not_tracked(critical)
    check_env_example_clean(critical)
    check_runtime_config(critical)
    check_source_for_secrets(critical)
    check_pip_audit(critical)
    print()
    if critical:
        print(f"\x1b[31m{len(critical)} critical finding(s):\x1b[0m")
        for item in critical:
            print(f"  - {item}")
        return 1
    print("\x1b[32mAll critical checks passed.\x1b[0m")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
