import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  cusat_id TEXT UNIQUE NOT NULL,
  role TEXT DEFAULT 'student',
  trust_score INTEGER DEFAULT 100,
  verified BOOLEAN DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS otps (
  email TEXT PRIMARY KEY,
  code_hash TEXT, expires_at TIMESTAMP, attempts INTEGER DEFAULT 0,
  pending_name TEXT, pending_cusat_id TEXT
);
CREATE TABLE IF NOT EXISTS issues (
  id TEXT PRIMARY KEY,
  title TEXT, category TEXT,
  building TEXT, floor TEXT,
  lat REAL, lng REAL,
  status TEXT DEFAULT 'OPEN',
  severity INTEGER, emergency INTEGER, complexity INTEGER,
  threat_level TEXT,
  unique_reporters INTEGER DEFAULT 1,
  priority REAL,
  rank_reason TEXT, summary TEXT,
  work_order_en TEXT, work_order_ml TEXT, trade_needed TEXT,
  needs_human_check BOOLEAN DEFAULT 0,
  failed_fix_attempts INTEGER DEFAULT 0,
  fix_disputed BOOLEAN DEFAULT 0,
  verify_deadline TIMESTAMP,
  created_at TIMESTAMP, resolved_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  issue_id TEXT REFERENCES issues(id),
  user_id INTEGER REFERENCES users(id),
  image_path TEXT, image_phash TEXT,
  note TEXT,
  lat REAL, lng REAL, gps_lat REAL, gps_lng REAL,
  building TEXT, floor TEXT,
  ai_description TEXT, advice TEXT,
  category TEXT,
  severity INTEGER, emergency INTEGER, complexity INTEGER,
  confidence REAL,
  hazard_box TEXT,
  merge_type TEXT, merge_reason TEXT,
  counts_toward_total BOOLEAN DEFAULT 1,
  status TEXT DEFAULT 'ACTIVE',
  created_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audits (
  id INTEGER PRIMARY KEY,
  issue_id TEXT REFERENCES issues(id),
  kind TEXT,
  user_id INTEGER REFERENCES users(id),
  image_path TEXT, image_phash TEXT,
  same_location_verified BOOLEAN,
  passed BOOLEAN,
  reason TEXT,
  created_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS issue_links (
  issue_a TEXT, issue_b TEXT, note TEXT, created_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS agent_events (
  id INTEGER PRIMARY KEY,
  report_id TEXT, step INTEGER,
  kind TEXT,
  text TEXT, created_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ledger (
  block_no INTEGER PRIMARY KEY,
  event TEXT, issue_id TEXT, report_id TEXT, actor TEXT,
  payload TEXT, prev_hash TEXT, block_hash TEXT,
  created_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS capture_tokens (
  token TEXT PRIMARY KEY, user_id INTEGER, expires_at TIMESTAMP, used BOOLEAN DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_report ON agent_events(report_id, id);
CREATE INDEX IF NOT EXISTS idx_reports_issue ON reports(issue_id);
"""

TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS no_delete_issues BEFORE DELETE ON issues
BEGIN SELECT RAISE(ABORT, 'Issues cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_reports BEFORE DELETE ON reports
BEGIN SELECT RAISE(ABORT, 'Reports cannot be deleted'); END;
CREATE TRIGGER IF NOT EXISTS no_change_ledger BEFORE UPDATE ON ledger
BEGIN SELECT RAISE(ABORT, 'Ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS no_delete_ledger BEFORE DELETE ON ledger
BEGIN SELECT RAISE(ABORT, 'Ledger is append-only'); END;
"""


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        conn.executescript(TRIGGERS)
        # Added after the first schema: severity/emergency bump applied each time a repair fails verification.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(issues)")}
        if "escalation" not in cols:
            conn.execute("ALTER TABLE issues ADD COLUMN escalation INTEGER DEFAULT 0")


def next_id(conn, table, prefix):
    row = conn.execute(f"SELECT id FROM {table} WHERE id LIKE ? ORDER BY id DESC LIMIT 1", (prefix + "-%",)).fetchone()
    n = int(row["id"].split("-")[1]) + 1 if row else 1
    return f"{prefix}-{n:04d}"


def rows(cursor):
    return [dict(r) for r in cursor.fetchall()]
