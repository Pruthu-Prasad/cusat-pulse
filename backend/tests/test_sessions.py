"""Sign-in sessions: real server-side sessions, revocation, expiry, and the forged-token hole being closed."""
import datetime
import tempfile
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from core import config, database, sessions


def _fresh_db(monkeypatch):
    tmp = Path(tempfile.mkdtemp()) / "t.db"
    monkeypatch.setattr(config, "DB_PATH", tmp)
    monkeypatch.setattr(database, "DB_PATH", tmp)
    from scripts import seed_cusat
    seed_cusat.seed(with_issues=False)
    return tmp


@pytest.fixture()
def client(monkeypatch):
    _fresh_db(monkeypatch)
    import main
    with TestClient(main.app) as c:
        yield c


def login(c, email="demo1@cusat.ac.in", ua="Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"):
    c.post("/api/auth/request-otp", json={"email": email})
    r = c.post("/api/auth/verify-otp", json={"email": email, "code": "000000"}, headers={"user-agent": ua})
    assert r.status_code == 200
    return {"Authorization": "Bearer " + r.json()["token"]}


def db_rows(sql, *args):
    conn = database.connect()
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def sql(statement, *args):
    conn = database.connect()
    try:
        conn.execute(statement, args)
        conn.commit()
    finally:
        conn.close()


def test_login_creates_a_working_session(client):
    h = login(client)
    assert client.get("/api/me", headers=h).status_code == 200
    assert len(db_rows("SELECT * FROM sessions")) == 1


def test_token_is_never_stored_only_its_hash(client):
    h = login(client)
    token = h["Authorization"][7:]
    stored = " ".join(str(v) for row in db_rows("SELECT * FROM sessions") for v in tuple(row))
    assert token not in stored
    assert sessions.hash_token(token) in stored


def test_forged_admin_token_signed_with_the_default_secret_is_rejected(client):
    """The old design accepted this: anyone could mint an admin token with no sign-in."""
    admin_id = db_rows("SELECT id FROM users WHERE email='estate@cusat.ac.in'")[0][0]
    forged = jwt.encode({"sub": str(admin_id), "role": "admin",
                         "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)},
                        "change-me", algorithm="HS256")
    r = client.get("/api/ledger/verify", headers={"Authorization": "Bearer " + forged})
    assert r.status_code == 401


def test_logout_really_ends_the_session(client):
    h = login(client)
    assert client.post("/api/auth/logout", headers=h).json() == {"ok": True}
    r = client.get("/api/me", headers=h)
    assert r.status_code == 401 and "sign in again" in r.json()["detail"]
    assert db_rows("SELECT * FROM sessions") == []


def test_logout_only_ends_this_device(client):
    phone, laptop = login(client), login(client, ua="Mozilla/5.0 (Windows NT 10.0) Chrome/120 Safari/537.36")
    client.post("/api/auth/logout", headers=phone)
    assert client.get("/api/me", headers=phone).status_code == 401
    assert client.get("/api/me", headers=laptop).status_code == 200


def test_logout_all_ends_every_device_of_that_account_only(client):
    a1, a2, other = login(client), login(client), login(client, "demo2@cusat.ac.in")
    assert client.post("/api/auth/logout-all", headers=a1).json() == {"ok": True, "revoked": 2}
    assert client.get("/api/me", headers=a1).status_code == 401
    assert client.get("/api/me", headers=a2).status_code == 401
    assert client.get("/api/me", headers=other).status_code == 200


def test_session_list_labels_devices_and_marks_this_one(client):
    phone = login(client)
    login(client, ua="Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36 Chrome/120 Safari/537.36 Edg/120")
    listed = client.get("/api/auth/sessions", headers=phone).json()["sessions"]
    assert len(listed) == 2
    assert [s["current"] for s in listed].count(True) == 1
    assert {s["device"] for s in listed} == {"Chrome on Android", "Edge on Windows"}
    assert all(set(s) == {"id", "device", "created_at", "last_seen_at", "current"} for s in listed)


def test_revoke_one_other_device(client):
    phone, laptop = login(client), login(client)
    other = next(s for s in client.get("/api/auth/sessions", headers=phone).json()["sessions"] if not s["current"])
    assert client.post(f"/api/auth/sessions/{other['id']}/revoke", headers=phone).json() == {"ok": True}
    assert client.get("/api/me", headers=laptop).status_code == 401
    assert client.get("/api/me", headers=phone).status_code == 200


def test_cannot_revoke_someone_elses_session(client):
    mine, theirs = login(client), login(client, "demo2@cusat.ac.in")
    theirs_id = client.get("/api/auth/sessions", headers=theirs).json()["sessions"][0]["id"]
    assert client.post(f"/api/auth/sessions/{theirs_id}/revoke", headers=mine).status_code == 404
    assert client.get("/api/me", headers=theirs).status_code == 200


def test_expired_session_is_rejected_and_cleaned_up(client):
    h = login(client)
    sql("UPDATE sessions SET expires_at='2000-01-01T00:00:00Z'")
    assert client.get("/api/me", headers=h).status_code == 401
    assert db_rows("SELECT * FROM sessions") == []


def test_hard_cap_applies_even_to_an_active_session(client):
    h = login(client)
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=config.SESSION_MAX_DAYS + 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql("UPDATE sessions SET created_at=?", old)  # still inside its sliding window, but older than the cap
    assert client.get("/api/me", headers=h).status_code == 401


def test_using_a_session_slides_its_expiry_forward(client):
    h = login(client)
    long_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    soon = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sql("UPDATE sessions SET last_seen_at=?, expires_at=?", long_ago, soon)
    assert client.get("/api/me", headers=h).status_code == 200
    row = db_rows("SELECT last_seen_at, expires_at FROM sessions")[0]
    assert row["last_seen_at"] > long_ago and row["expires_at"] > soon


def test_session_survives_a_backend_restart(client):
    """Sessions are in the database, so restarting the server keeps people signed in."""
    h = login(client)
    import main
    with TestClient(main.app) as restarted:  # a fresh app instance: startup runs again
        assert restarted.get("/api/me", headers=h).status_code == 200


def test_resetting_the_database_signs_everyone_out(client, monkeypatch):
    h = login(client)
    _fresh_db(monkeypatch)  # what `seed_cusat --fresh` does: a new empty database
    assert client.get("/api/me", headers=h).status_code == 401


def test_query_string_token_still_works_for_images_and_streams(client):
    h = login(client, "estate@cusat.ac.in")
    token = h["Authorization"][7:]
    assert client.get(f"/api/me?token={token}").status_code == 200
    assert client.get("/api/me?token=not-a-real-token").status_code == 401


def test_staff_and_admin_rules_still_enforced(client):
    student, staff, admin = login(client), login(client, "itsupport@cusat.ac.in"), login(client, "estate@cusat.ac.in")
    assert client.get("/api/admin/heatmap", headers=student).status_code == 403
    assert client.get("/api/admin/heatmap", headers=staff).status_code == 200
    assert client.get("/api/ledger/verify", headers=staff).status_code == 403
    assert client.get("/api/ledger/verify", headers=admin).status_code == 200


def test_device_cap_keeps_the_newest(client, monkeypatch):
    monkeypatch.setattr(sessions, "MAX_SESSIONS_PER_USER", 3)
    tokens = [login(client) for _ in range(5)]
    assert client.get("/api/me", headers=tokens[0]).status_code == 401
    assert client.get("/api/me", headers=tokens[1]).status_code == 401
    assert all(client.get("/api/me", headers=t).status_code == 200 for t in tokens[2:])


def test_purge_removes_only_expired_sessions(client):
    keep, drop = login(client), login(client, "demo2@cusat.ac.in")
    sql("UPDATE sessions SET expires_at='2000-01-01T00:00:00Z' WHERE user_id=(SELECT id FROM users WHERE email='demo2@cusat.ac.in')")
    conn = database.connect()
    try:
        assert sessions.purge_expired(conn) == 1
        conn.commit()
    finally:
        conn.close()
    assert client.get("/api/me", headers=keep).status_code == 200
    assert client.get("/api/me", headers=drop).status_code == 401


@pytest.mark.parametrize("ua,label", [
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1", "Safari on iPhone"),
    ("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36", "Chrome on Android"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36 Edg/120.0", "Edge on Windows"),
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/121.0", "Firefox on Mac"),
    ("", "Unknown device"),
])
def test_device_labels(ua, label):
    assert sessions.device_label(ua) == label
