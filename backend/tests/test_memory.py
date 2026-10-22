from app import db
from app.memory import create_record, normalise_topic, update_status, events_for


def _mkproject(name="t"):
    with db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects(name, created_at) VALUES (?, ?)", [name, db.now_iso()]
        )
        return cur.lastrowid


def test_normalise_topic_handles_variants():
    assert normalise_topic("Auth on get_order") == normalise_topic("get_order authentication")
    assert normalise_topic("Deployment target") != normalise_topic("Stripe retry policy")


def test_conflicting_topic_marks_prior_record():
    pid = _mkproject()
    a = create_record(pid, "Auth on get_order", "First version", verification_status="verified")
    b = create_record(pid, "get_order authentication", "Different wording, same topic", verification_status="unverified")
    assert a["id"] != b["id"]
    with db.connect() as conn:
        row = conn.execute("SELECT verification_status FROM memory_records WHERE id = ?", [a["id"]]).fetchone()
    assert row["verification_status"] == "conflicting"


def test_update_status_logs_event():
    pid = _mkproject()
    r = create_record(pid, "Deployment target", "Fly.io, two regions", verification_status="unverified")
    update_status(r["id"], "verified", reason="Confirmed with Priya")
    events = events_for(r["id"])
    assert len(events) >= 2
    latest = events[0]
    assert latest["to_status"] == "verified"
    assert "Confirmed" in latest["reason"]
