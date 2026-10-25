import hashlib
import json

from core.database import get_db, now_iso, rows

GENESIS = "0" * 64
PAGE_SIZE = 50


def _hash(prev_hash, payload):
    return hashlib.sha256((prev_hash + payload).encode()).hexdigest()


def write_block(conn, event, issue_id=None, report_id=None, actor="system", data=None):
    """Append one block. Put "status" in data for any event that changes an issue's status."""
    last = conn.execute("SELECT block_no, block_hash FROM ledger ORDER BY block_no DESC LIMIT 1").fetchone()
    n = last["block_no"] + 1 if last else 1
    prev_hash = last["block_hash"] if last else GENESIS
    created_at = now_iso()
    payload = json.dumps({
        "block_no": n,
        "event": event,
        "issue_id": issue_id,
        "report_id": report_id,
        "actor": actor,
        "data": data or {},
        "created_at": created_at,
    }, sort_keys=True)
    block_hash = _hash(prev_hash, payload)
    conn.execute(
        "INSERT INTO ledger (block_no, event, issue_id, report_id, actor, payload, prev_hash, block_hash, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (n, event, issue_id, report_id, actor, payload, prev_hash, block_hash, created_at),
    )
    return block_hash


def verify(conn):
    blocks = conn.execute("SELECT * FROM ledger ORDER BY block_no").fetchall()
    prev = GENESIS
    expected_status = {}
    for b in blocks:
        payload = json.loads(b["payload"])
        # Columns must agree with the signed payload, and the hash must chain.
        mismatch = (
            b["prev_hash"] != prev
            or _hash(prev, b["payload"]) != b["block_hash"]
            or payload.get("issue_id") != b["issue_id"]
            or payload.get("event") != b["event"]
            or payload.get("report_id") != b["report_id"]
        )
        if mismatch:
            return {"intact": False, "broken_at": b["block_no"], "issue_id": payload.get("issue_id") or b["issue_id"],
                    "reason": "Block contents do not match its hash", "blocks": len(blocks)}
        status = payload.get("data", {}).get("status")
        if status and payload.get("issue_id"):
            expected_status[payload["issue_id"]] = (status, b["block_no"])
        prev = b["block_hash"]

    for issue_id, (status, block_no) in expected_status.items():
        row = conn.execute("SELECT status FROM issues WHERE id=?", (issue_id,)).fetchone()
        if row and row["status"] != status:
            return {"intact": False, "broken_at": block_no, "issue_id": issue_id,
                    "reason": f"Issue status is {row['status']} but the ledger says {status}", "blocks": len(blocks)}
    return {"intact": True, "blocks": len(blocks), "latest_hash": prev}


def page(issue_id=None, page_no=1):
    """Newest blocks first, optionally for one issue."""
    with get_db() as conn:
        where, args = ("WHERE issue_id=?", [issue_id]) if issue_id else ("", [])
        blocks = rows(conn.execute(
            f"SELECT block_no, event, issue_id, report_id, actor, prev_hash, block_hash, created_at FROM ledger {where}"
            " ORDER BY block_no DESC LIMIT ? OFFSET ?", (*args, PAGE_SIZE, (page_no - 1) * PAGE_SIZE)))
        total = conn.execute(f"SELECT COUNT(*) c FROM ledger {where}", args).fetchone()["c"]
        latest = conn.execute("SELECT block_hash FROM ledger ORDER BY block_no DESC LIMIT 1").fetchone()
    return {"blocks": blocks, "total": total, "latest_hash": latest["block_hash"] if latest else None}


def verify_now():
    with get_db() as conn:
        return verify(conn)
