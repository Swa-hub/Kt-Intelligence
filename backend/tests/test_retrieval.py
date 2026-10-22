from pathlib import Path

from app import db
from app.ingestion import save_source_and_chunks
from app.retrieval import search


def _mkproject(name="t"):
    with db.connect() as conn:
        cur = conn.execute("INSERT INTO projects(name, created_at) VALUES (?, ?)", [name, db.now_iso()])
        return cur.lastrowid


def test_bm25_retrieves_relevant_chunk(tmp_path: Path):
    pid = _mkproject()
    f = tmp_path / "routes.py"
    f.write_text(
        "@bp.get('/orders/<int:order_id>')\n@rate_limit\n"
        "def get_order(order_id):\n    return row\n\n"
        "@bp.post('/orders')\n@require_auth\n"
        "def create_order():\n    pass\n"
    )
    save_source_and_chunks(pid, "routes.py", f, "code")
    hits = search(pid, "require_auth decorator on endpoints", k=3)
    assert hits
    assert any("require_auth" in h.text for h in hits)
