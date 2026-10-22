"""Shared test fixtures. Each test gets an isolated SQLite + upload dir."""
import os
import shutil
import tempfile

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    """Point every test at its own temp data directory and reload settings."""
    data = tmp_path / "data"
    uploads = data / "uploads"
    data.mkdir(parents=True, exist_ok=True)
    uploads.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("DATA_DIR", str(data))
    monkeypatch.setenv("SQLITE_PATH", str(data / "kt.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(uploads))
    monkeypatch.setenv("LLM_API_KEY", "")  # tests should not accidentally call live

    # Reload the config module so new env vars take effect.
    import importlib
    from app import config as _config
    importlib.reload(_config)
    from app import db as _db
    importlib.reload(_db)
    _db.init_db()

    yield

    shutil.rmtree(data, ignore_errors=True)
