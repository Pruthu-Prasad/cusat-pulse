import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request

from core import sessions
from core.config import ALLOWED_EMAIL_DOMAINS, DEMO_MODE, DEMO_OTP, JWT_SECRET, STAFF_EMAILS
from core.database import get_db, now_iso, parse_iso
from services import mailer

DEMO_EMAIL_PREFIX = "demo"


def normalize_cusat_id(cusat_id):
    return "".join((cusat_id or "").split()).upper()


def role_for(email):
    if not STAFF_EMAILS or email not in STAFF_EMAILS:
        return "student"
    return "admin" if email == STAFF_EMAILS[0] else "staff"


def _hash_code(email, code):
    return hashlib.sha256(f"{email}:{code}:{JWT_SECRET}".encode()).hexdigest()


def is_demo_account(email):
    return DEMO_MODE and (email.startswith(DEMO_EMAIL_PREFIX) or email in STAFF_EMAILS)


def allowed_email(email):
    """cusat.ac.in and any subdomain of it (pg.cusat.ac.in, ug.cusat.ac.in, ...)."""
    domain = email.rpartition("@")[2]
    return "@" in email and any(domain == d or domain.endswith("." + d) for d in ALLOWED_EMAIL_DOMAINS)


def request_otp(name, email, cusat_id):
    email = (email or "").strip().lower()
    if not allowed_email(email):
        raise HTTPException(400, "Only CUSAT email addresses can sign in.")
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        cid = normalize_cusat_id(cusat_id)
        if not user:
            if not (name or "").strip() or not cid:
                raise HTTPException(400, "First time here? Please enter your name and CUSAT ID.")
            other = conn.execute("SELECT email FROM users WHERE cusat_id=?", (cid,)).fetchone()
            if other and other["email"] != email:
                raise HTTPException(400, "This CUSAT ID is already registered.")
        code = f"{secrets.randbelow(10**6):06d}"
        expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT OR REPLACE INTO otps (email, code_hash, expires_at, attempts, pending_name, pending_cusat_id)"
            " VALUES (?,?,?,0,?,?)",
            (email, _hash_code(email, code), expires, (name or "").strip(), cid),
        )
    if is_demo_account(email):
        # Demo inboxes don't exist; they sign in with DEMO_OTP.
        print(f"\n==== OTP for {email}: {code} ====\n", flush=True)
    else:
        mailer.send_otp(email, code)
    return {"sent": True, "new_user": user is None, "demo_hint": DEMO_OTP if is_demo_account(email) else None}


def verify_otp(email, code, user_agent=None):
    email = (email or "").strip().lower()
    with get_db() as conn:
        otp = conn.execute("SELECT * FROM otps WHERE email=?", (email,)).fetchone()
        if not otp:
            raise HTTPException(400, "Please request a code first.")
        if otp["attempts"] >= 5:
            raise HTTPException(400, "Too many tries. Request a new code.")
        if parse_iso(otp["expires_at"]) < datetime.now(timezone.utc):
            raise HTTPException(400, "This code has expired. Request a new one.")
        ok = _hash_code(email, code) == otp["code_hash"] or (is_demo_account(email) and code == DEMO_OTP)
        if not ok:
            conn.execute("UPDATE otps SET attempts = attempts + 1 WHERE email=?", (email,))
            raise HTTPException(400, "That code is not right.")
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not user:
            conn.execute(
                "INSERT INTO users (name, email, cusat_id, role, verified, created_at) VALUES (?,?,?,?,1,?)",
                (otp["pending_name"], email, otp["pending_cusat_id"], role_for(email), now_iso()),
            )
            user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.execute("UPDATE users SET verified=1 WHERE id=?", (user["id"],))
        conn.execute("UPDATE otps SET attempts = 99 WHERE email=?", (email,))
        token = sessions.create(conn, user["id"], user_agent)
        return {"token": token, "user": public_user(dict(user))}


def public_user(u):
    return {k: u[k] for k in ("id", "name", "email", "cusat_id", "role", "trust_score")}


def token_from_request(request: Request):
    """Bearer header, or ?token= for places that can't set headers (<img> tags, EventSource)."""
    header = request.headers.get("authorization", "")
    return header[7:] if header.lower().startswith("bearer ") else request.query_params.get("token")


def current_user(request: Request):
    token = token_from_request(request)
    if not token:
        raise HTTPException(401, "Please sign in.")
    with get_db() as conn:
        session = sessions.lookup(conn, token)
        user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone() if session else None
    if not session or not user:
        raise HTTPException(401, "Your session has expired. Please sign in again.")
    return dict(user)


def require_staff(user=Depends(current_user)):
    if user["role"] not in ("staff", "admin"):
        raise HTTPException(403, "Staff only.")
    return user


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only.")
    return user


def actor(user):
    return f"{user['role']}:{user['cusat_id']}"
