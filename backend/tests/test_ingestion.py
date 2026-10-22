from pathlib import Path

from app import db
from app.ingestion import save_source_and_chunks


def _mkproject(name="t"):
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects(name, created_at) VALUES (?, ?)",
            [name, db.now_iso()],
        )
        return cur.lastrowid


def test_upload_creates_chunks(tmp_path: Path):
    pid = _mkproject()
    f = tmp_path / "note.md"
    f.write_text("# A document\n\nSome paragraph that discusses things.\n")
    r = save_source_and_chunks(pid, "note.md", f, "doc")
    assert r["chunks"] >= 1
    assert r["kind"] == "doc"
    assert "unchanged" not in r


def test_identical_reupload_is_idempotent(tmp_path: Path):
    pid = _mkproject()
    f = tmp_path / "x.py"
    f.write_text("def foo():\n    return 1\n")
    first = save_source_and_chunks(pid, "x.py", f, "code")

    # Re-upload the exact same bytes to a fresh path
    f2 = tmp_path / "x_again.py"
    f2.write_bytes(f.read_bytes())
    second = save_source_and_chunks(pid, "x.py", f2, "code")
    assert second["unchanged"] is True
    assert second["source_id"] == first["source_id"]


def test_modified_reupload_supersedes(tmp_path: Path):
    pid = _mkproject()
    f = tmp_path / "x.py"
    f.write_text("def foo():\n    return 1\n")
    first = save_source_and_chunks(pid, "x.py", f, "code")

    f.write_text("def foo():\n    return 2\n")
    second = save_source_and_chunks(pid, "x.py", f, "code")
    assert second.get("replaced_source_id") == first["source_id"]
    assert second["source_id"] != first["source_id"]
