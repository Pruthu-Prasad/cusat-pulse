"""Ledger tamper demo for judges.

Run from backend/:
python -m scripts.tamper_demo            backs up the DB, quietly edits one old block, then restores the trigger
python -m scripts.tamper_demo --status   instead changes an issue's status directly (caught by the status cross-check)
python -m scripts.tamper_demo --restore  puts the backup back
"""
import shutil
import sqlite3
import sys

from core.config import DB_PATH

BACKUP = DB_PATH.with_name("cusat_pulse.backup.db")


def main():
    if "--restore" in sys.argv:
        if not BACKUP.exists():
            print("No backup found.")
            return
        for suffix in ("-wal", "-shm"):
            p = DB_PATH.with_name(DB_PATH.name + suffix)
            if p.exists():
                p.unlink()
        shutil.copy(BACKUP, DB_PATH)
        print("Restored the database from backup. Chain is intact again.")
        return

    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(BACKUP)
    src.backup(dst)  # consistent copy even with WAL
    dst.close()
    print(f"Backed up to {BACKUP.name}")
    try:
        _tamper(src)
    finally:
        src.close()  # release the DB file so --restore can replace it


def _tamper(conn):
    if "--status" in sys.argv:
        row = conn.execute("SELECT id, status FROM issues WHERE status != 'RESOLVED' ORDER BY priority DESC LIMIT 1").fetchone()
        conn.execute("UPDATE issues SET status='RESOLVED' WHERE id=?", (row[0],))
        conn.commit()
        print(f"Quietly marked {row[0]} as RESOLVED in the database (it was {row[1]}).")
        return

    total = conn.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
    target = min(14, max(1, total // 3))
    row = conn.execute("SELECT block_no, issue_id, event FROM ledger WHERE block_no >= ? AND issue_id IS NOT NULL"
                       " ORDER BY block_no LIMIT 1", (target,)).fetchone()
    conn.execute("DROP TRIGGER no_change_ledger")
    conn.execute("UPDATE ledger SET issue_id = 'CL-9999' WHERE block_no=?", (row[0],))
    conn.execute("CREATE TRIGGER no_change_ledger BEFORE UPDATE ON ledger "
                 "BEGIN SELECT RAISE(ABORT, 'Ledger is append-only'); END;")
    conn.commit()
    print(f"Dropped the trigger, changed block #{row[0]} ({row[2]} on {row[1]}) to point at CL-9999, put the trigger back.")
    print("Now click 'Verify chain' on the Ledger tab.")


if __name__ == "__main__":
    main()
