"""Parts the API snapshot can't reach: the scheduler loop's jobs and the demo scripts. Uses a temp DB."""
import tempfile
from pathlib import Path

import pytest

from core import config, database
from services.ledger import verify, write_block


@pytest.fixture()
def db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    monkeypatch.setattr(config, "DB_PATH", tmp)
    monkeypatch.setattr(database, "DB_PATH", tmp)
    from scripts import seed_cusat
    seed_cusat.seed()
    conn = database.connect()
    yield conn
    conn.close()


def status(conn, issue_id):
    return conn.execute("SELECT status FROM issues WHERE id=?", (issue_id,)).fetchone()[0]


def test_verification_window_expiry_auto_resolves(db):
    from services import scheduler
    db.execute("UPDATE issues SET status='AWAITING_STUDENT_CHECK', verify_deadline='2000-01-01T00:00:00Z' WHERE id='CL-0005'")
    write_block(db, "AUDIT_PASSED", "CL-0005", None, "gemma", {"status": "AWAITING_STUDENT_CHECK"})
    db.commit()
    scheduler.close_expired()
    assert status(db, "CL-0005") == "RESOLVED"
    assert verify(db)["intact"]


def test_window_not_expired_stays_open(db):
    from services import scheduler
    db.execute("UPDATE issues SET status='AWAITING_STUDENT_CHECK', verify_deadline='2999-01-01T00:00:00Z' WHERE id='CL-0005'")
    write_block(db, "AUDIT_PASSED", "CL-0005", None, "gemma", {"status": "AWAITING_STUDENT_CHECK"})
    db.commit()
    scheduler.close_expired()
    assert status(db, "CL-0005") == "AWAITING_STUDENT_CHECK"


def test_issue_without_valid_reports_is_dismissed(db):
    from services import scheduler
    db.execute("UPDATE reports SET status='MARKED_FAKE' WHERE issue_id='CL-0004'")
    db.commit()
    scheduler.close_expired()
    assert status(db, "CL-0004") == "DISMISSED"
    assert verify(db)["intact"]


def test_rerank_all_runs(db):
    from services import scheduler
    scheduler.rerank_all()
    assert db.execute("SELECT COUNT(*) FROM issues WHERE priority > 0").fetchone()[0] == 6


def test_seed_refuses_to_double_seed(db):
    from scripts import seed_cusat
    r = seed_cusat.seed()
    assert r["seeded"] is False and "python -m scripts.seed_cusat --fresh" in r["message"]


def test_tamper_demo_breaks_chain_and_restore_fixes_it(db, monkeypatch):
    from scripts import tamper_demo
    backup = config.DB_PATH.with_name("backup.db")
    monkeypatch.setattr(tamper_demo, "DB_PATH", config.DB_PATH)
    monkeypatch.setattr(tamper_demo, "BACKUP", backup)
    db.close()
    monkeypatch.setattr("sys.argv", ["tamper_demo"])
    tamper_demo.main()
    with database.get_db() as conn:
        broken = verify(conn)
    assert broken["intact"] is False and broken["broken_at"]
    monkeypatch.setattr("sys.argv", ["tamper_demo", "--restore"])
    tamper_demo.main()
    with database.get_db() as conn:
        assert verify(conn)["intact"] is True


def test_paths_point_at_backend_folder():
    # config.py moved into core/; data must still live in backend/
    assert config.BASE_DIR.name == "backend"
    assert (config.BASE_DIR / "main.py").exists()
    assert config.UPLOAD_DIR == config.BASE_DIR / "uploads"
