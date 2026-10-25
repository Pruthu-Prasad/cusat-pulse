import asyncio

from core.database import get_db, now_iso
from services import ranking
from services.ledger import write_block

CHECK_EVERY_S = 15
RERANK_EVERY_TICKS = 40  # ~10 minutes, keeps the age bonus current


def close_expired():
    with get_db() as conn:
        due = conn.execute("SELECT id FROM issues WHERE status='AWAITING_STUDENT_CHECK' AND verify_deadline <= ?",
                           (now_iso(),)).fetchall()
        for r in due:
            conn.execute("UPDATE issues SET status='RESOLVED', resolved_at=?, verify_deadline=NULL WHERE id=?",
                         (now_iso(), r["id"]))
            write_block(conn, "RESOLVED", r["id"], None, "system",
                        {"status": "RESOLVED", "reason": "No dispute before the deadline"})
        # Safety net: any open issue whose reports have all been ruled invalid is closed as dismissed.
        for r in conn.execute("SELECT id FROM issues WHERE status NOT IN ('RESOLVED','DISMISSED')").fetchall():
            ranking.dismiss_if_no_reports(conn, r["id"], "system", "No valid reports remain")


def rerank_all():
    with get_db() as conn:
        for r in conn.execute("SELECT id FROM issues WHERE status NOT IN ('RESOLVED','DISMISSED')").fetchall():
            ranking.recount(conn, r["id"])


async def scheduler_loop():
    tick = 0
    while True:
        try:
            await asyncio.to_thread(close_expired)
            if tick % RERANK_EVERY_TICKS == 0:
                await asyncio.to_thread(rerank_all)
        except Exception as e:
            print(f"[scheduler] {e!r}", flush=True)
        tick += 1
        await asyncio.sleep(CHECK_EVERY_S)
