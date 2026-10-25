import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/ (this file is backend/core/config.py)
load_dotenv(BASE_DIR / ".env")


def _list(name, default=""):
    return [x.strip().lower() for x in os.getenv(name, default).split(",") if x.strip()]


GEMINI_KEYS = [k.strip() for k in (os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY", "")).split(",") if k.strip()]
GEMMA_MODEL = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
ALLOWED_EMAIL_DOMAINS = _list("ALLOWED_EMAIL_DOMAINS", "cusat.ac.in")
STAFF_EMAILS = _list("STAFF_EMAILS", "estate@cusat.ac.in,itsupport@cusat.ac.in")
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
DEMO_OTP = os.getenv("DEMO_OTP", "000000")
# OTP email. Leave SMTP_USER / SMTP_PASSWORD empty to print codes to the console instead.
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
VERIFY_WINDOW_MINUTES = int(os.getenv("VERIFY_WINDOW_MINUTES", "1440"))
MERGE_RADIUS_METERS = float(os.getenv("MERGE_RADIUS_METERS", "50"))
MAX_REPORTS_PER_HOUR = int(os.getenv("MAX_REPORTS_PER_HOUR", "5"))
# A new report of the same problem inside this window after "resolved" means the fix did not hold: reopen, don't duplicate.
REOPEN_WINDOW_HOURS = float(os.getenv("REOPEN_WINDOW_HOURS", "72"))
# Sign-in sessions (stored in the database): each one slides forward while it is used, up to a hard cap.
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "7"))
SESSION_MAX_DAYS = int(os.getenv("SESSION_MAX_DAYS", "30"))
MAX_SESSIONS_PER_USER = int(os.getenv("MAX_SESSIONS_PER_USER", "20"))  # bounds the table; generous so shared demo logins never kick each other out

DB_PATH = BASE_DIR / "cusat_pulse.db"
UPLOAD_DIR = BASE_DIR / "uploads"
SEED_IMAGE_DIR = BASE_DIR / "seed_images"
DEMO_CACHE_PATH = BASE_DIR / "demo_cache.json"
UPLOAD_DIR.mkdir(exist_ok=True)
SEED_IMAGE_DIR.mkdir(exist_ok=True)
