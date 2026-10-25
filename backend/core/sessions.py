"""Server-side sign-in sessions.

A session is a random opaque token. Only its SHA-256 is stored, so a leaked database can't be used to sign in, and
nothing can be forged without a real sign-in. Because the session lives in the database:
  - signing out (or "sign out everywhere") really ends it, immediately;
  - it survives a backend restart (users stay signed in, like any production site);
  - resetting the database (seed --fresh) signs everyone out.
A session slides forward while it is used (SESSION_DAYS) up to a hard cap (SESSION_MAX_DAYS).
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from core.config import MAX_SESSIONS_PER_USER, SESSION_DAYS, SESSION_MAX_DAYS
from core.database import parse_iso

TOUCH_EVERY = timedelta(minutes=5)  # refresh "last seen" at most this often, not on every request


def _fmt(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def public_id(token_hash):
    """Short id shown to the user to pick a device; not enough to sign in."""
    return token_hash[:12]


def device_label(user_agent):
    ua = user_agent or ""
    if not ua:
        return "Unknown device"
    system = next((name for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
                                          ("Windows", "Windows"), ("Macintosh", "Mac"), ("Mac OS X", "Mac"),
                                          ("Linux", "Linux")) if key in ua), "Unknown system")
    browser = next((name for key, name in (("Edg/", "Edge"), ("OPR/", "Opera"), ("SamsungBrowser", "Samsung Internet"),
                                           ("Firefox/", "Firefox"), ("CriOS", "Chrome"), ("Chrome/", "Chrome"),
                                           ("Safari/", "Safari")) if key in ua), "Browser")
    return f"{browser} on {system}"


def create(conn, user_id, user_agent=None):
    """Start a session and return its token (the only time the token exists in readable form)."""
    now = datetime.now(timezone.utc)
    conn.execute("DELETE FROM sessions WHERE user_id=? AND expires_at <= ?", (user_id, _fmt(now)))
    token = secrets.token_urlsafe(32)
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, last_seen_at, expires_at, user_agent) VALUES (?,?,?,?,?,?)",
        (hash_token(token), user_id, _fmt(now), _fmt(now), _fmt(now + timedelta(days=SESSION_DAYS)), (user_agent or "")[:300]))
    conn.execute(
        "DELETE FROM sessions WHERE user_id=? AND token_hash NOT IN"
        " (SELECT token_hash FROM sessions WHERE user_id=? ORDER BY last_seen_at DESC, rowid DESC LIMIT ?)",
        (user_id, user_id, MAX_SESSIONS_PER_USER))
    return token


def lookup(conn, token):
    """The session row for this token if it is still valid (sliding its expiry forward), else None."""
    if not token:
        return None
    h = hash_token(token)
    row = conn.execute("SELECT * FROM sessions WHERE token_hash=?", (h,)).fetchone()
    if not row:
        return None
    now = datetime.now(timezone.utc)
    started = parse_iso(row["created_at"])
    hard_end = started + timedelta(days=SESSION_MAX_DAYS)
    if parse_iso(row["expires_at"]) <= now or hard_end <= now:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (h,))
        return None
    if now - parse_iso(row["last_seen_at"]) >= TOUCH_EVERY:
        conn.execute("UPDATE sessions SET last_seen_at=?, expires_at=? WHERE token_hash=?",
                     (_fmt(now), _fmt(min(now + timedelta(days=SESSION_DAYS), hard_end)), h))
    return row


def revoke(conn, token):
    return conn.execute("DELETE FROM sessions WHERE token_hash=?", (hash_token(token),)).rowcount


def revoke_all(conn, user_id):
    return conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,)).rowcount


def revoke_by_public_id(conn, user_id, sid):
    """Sign out one device of this user. Returns how many were removed (0 = not theirs / not found)."""
    return conn.execute("DELETE FROM sessions WHERE user_id=? AND substr(token_hash,1,12)=?", (user_id, sid)).rowcount


def list_for(conn, user_id, current_token):
    current = hash_token(current_token) if current_token else None
    rows = conn.execute("SELECT * FROM sessions WHERE user_id=? ORDER BY last_seen_at DESC, rowid DESC", (user_id,)).fetchall()
    return [{"id": public_id(r["token_hash"]), "device": device_label(r["user_agent"]), "created_at": r["created_at"],
             "last_seen_at": r["last_seen_at"], "current": r["token_hash"] == current} for r in rows]


def purge_expired(conn):
    now = datetime.now(timezone.utc)
    cap = _fmt(now - timedelta(days=SESSION_MAX_DAYS))
    return conn.execute("DELETE FROM sessions WHERE expires_at <= ? OR created_at <= ?", (_fmt(now), cap)).rowcount
