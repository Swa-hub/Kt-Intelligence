"""Measurable benchmark against the orders-api demo scenario.

Produces concrete numbers for the pitch:
  - total bytes of KT material ingested
  - number of candidate claims examined
  - findings created, split by severity and extraction method
  - whether the hero planted-contradiction (missing @require_auth on
    get_order) was detected
  - total wall-clock time, broken down by stage

Usage:
  CLI:   python -m app.benchmark
  HTTP:  GET /api/benchmark
"""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

from . import gap_detector, nebius_client
from .config import settings
from .db import connect, init_db, now_iso
from .ingestion import save_source_and_chunks


SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent / "samples" / "demo-project"
SAMPLE_FILES = [
    ("transcript.txt", "transcript"),
    ("routes.py",      "code"),
    ("payments.py",    "code"),
    ("ORDR-412.md",    "doc"),
]

# The planted contradiction: `get_order` is missing @require_auth. A real
# hit mentions both the subject (get_order OR /orders/<id>) AND the auth
# concept in the title or explanation. Matching only on `@require_auth`
# string presence would false-positive on tangential findings whose code
# excerpts cite the decorator.
_HERO_SUBJECT = re.compile(r"get_order|/orders/<", re.IGNORECASE)
_HERO_CONCEPT = re.compile(r"auth|require", re.IGNORECASE)


def _is_hero(row) -> bool:
    text = f"{row['title'] or ''} {row.get('explanation') or ''}"
    return bool(_HERO_SUBJECT.search(text) and _HERO_CONCEPT.search(text))


def _bytes_of(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _mkproject(name: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects(name, description, created_at) VALUES (?, ?, ?)",
            [name, "Benchmark run", now_iso()],
        )
        return cur.lastrowid


def run(cleanup: bool = True) -> dict:
    """Run the orders-api demo scenario end-to-end and return metrics."""
    init_db()
    if not SAMPLE_DIR.exists():
        return {"error": f"Sample directory not found at {SAMPLE_DIR}"}

    project_id = _mkproject(f"benchmark-{int(time.time())}")
    bytes_ingested = 0

    t0 = time.perf_counter()

    target_dir = Path(settings.upload_dir) / f"project_{project_id}"
    target_dir.mkdir(parents=True, exist_ok=True)

    for fname, kind in SAMPLE_FILES:
        src = SAMPLE_DIR / fname
        if not src.exists():
            continue
        dest = target_dir / fname
        dest.write_bytes(src.read_bytes())
        bytes_ingested += _bytes_of(src)
        save_source_and_chunks(project_id, fname, dest, kind)

    t_ingest = time.perf_counter() - t0

    t1 = time.perf_counter()
    result = gap_detector.analyze_project(project_id)
    t_analyze = time.perf_counter() - t1

    with connect() as conn:
        rows = conn.execute(
            "SELECT severity, title, explanation, code_evidence_json FROM findings WHERE project_id = ?",
            [project_id],
        ).fetchall()

    by_sev: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    hero_detected = False
    for r in rows:
        by_sev[r["severity"]] = by_sev.get(r["severity"], 0) + 1
        if _is_hero(r):
            hero_detected = True

    if cleanup:
        with connect() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", [project_id])
        shutil.rmtree(target_dir, ignore_errors=True)

    return {
        "mode": "live" if nebius_client.is_configured() else "demo",
        "bytes_ingested": bytes_ingested,
        "files_ingested": len(SAMPLE_FILES),
        "claims_examined": result.get("claims_examined", 0),
        "findings_created": result.get("findings_created", 0),
        "findings_by_severity": by_sev,
        "extraction_method": result.get("extraction_method", "unknown"),
        "hero_contradiction_detected": hero_detected,
        "timings_sec": {
            "ingest": round(t_ingest, 2),
            "analyze": round(t_analyze, 2),
            "total":   round(t_ingest + t_analyze, 2),
        },
    }


def _pretty(d: dict) -> str:
    return json.dumps(d, indent=2, sort_keys=True)


def main() -> int:  # pragma: no cover
    """CLI entrypoint: `python -m app.benchmark`"""
    print("KT Intelligence benchmark · orders-api demo scenario")
    print("=" * 56)
    r = run(cleanup=True)
    print(_pretty(r))
    if "error" in r:
        return 1
    print("\nSummary:")
    print(f"  Ingested {r['bytes_ingested']:,} bytes across {r['files_ingested']} files in {r['timings_sec']['ingest']}s")
    print(f"  Examined {r['claims_examined']} candidate claims via {r['extraction_method']} extraction in {r['timings_sec']['analyze']}s")
    print(f"  Recorded {r['findings_created']} findings "
          f"({r['findings_by_severity']['high']} high / "
          f"{r['findings_by_severity']['medium']} medium / "
          f"{r['findings_by_severity']['low']} low)")
    print(f"  Hero contradiction detected: {r['hero_contradiction_detected']}")
    return 0 if r.get("hero_contradiction_detected") else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
