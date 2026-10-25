from datetime import datetime, timezone

import gemma
from config import STAFF_EMAILS
from db import now_iso, parse_iso
from ledger import write_block


def threat_level(severity):
    if severity >= 9:
        return "Critical"
    if severity >= 7:
        return "High"
    if severity >= 4:
        return "Medium"
    return "Low"


def age_bonus(created_at):
    hours = (datetime.now(timezone.utc) - parse_iso(created_at)).total_seconds() / 3600
    return min(2.0, 0.5 * int(hours // 12))


def breakdown(issue):
    s, e, c, r = issue["severity"] or 0, issue["emergency"] or 0, issue["complexity"] or 0, issue["unique_reporters"] or 0
    parts = {
        "severity": round(0.40 * s, 2),
        "emergency": round(0.25 * e, 2),
        "complexity": round(0.20 * c, 2),
        "reporters": round(0.15 * min(10, 2.5 * r), 2),
        "age": age_bonus(issue["created_at"]),
    }
    total = round(sum(parts.values()), 2)
    # Low-confidence issues don't rank above Medium until staff confirm.
    if issue.get("needs_human_check"):
        total = min(total, 6.0)
    return {"inputs": {"S": s, "E": e, "C": c, "R": r}, "parts": parts, "priority": total}


def recount(conn, issue_id, actor="system"):
    """Recompute scores, unique reporters, priority and threat level from the issue's active reports."""
    issue = dict(conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone())
    agg = conn.execute(
        "SELECT MAX(severity) s, MAX(emergency) e, MAX(complexity) c, MIN(confidence) conf,"
        " COUNT(DISTINCT CASE WHEN counts_toward_total=1 THEN user_id END) r"
        " FROM reports WHERE issue_id=? AND status='ACTIVE'",
        (issue_id,),
    ).fetchone()
    issue["unique_reporters"] = agg["r"] or 0  # always, so it drops to 0 when the last report is ruled fake
    if agg["s"] is not None:
        bump = issue.get("escalation") or 0
        issue.update(severity=min(10, agg["s"] + bump), emergency=min(10, agg["e"] + bump), complexity=agg["c"])
    issue["priority"] = breakdown(issue)["priority"]
    old_level = issue["threat_level"]
    issue["threat_level"] = threat_level(issue["severity"] or 1)
    conn.execute(
        "UPDATE issues SET severity=?, emergency=?, complexity=?, unique_reporters=?, priority=?, threat_level=? WHERE id=?",
        (issue["severity"], issue["emergency"], issue["complexity"], issue["unique_reporters"],
         issue["priority"], issue["threat_level"], issue_id),
    )
    changed = old_level is not None and old_level != issue["threat_level"]
    if changed:
        write_block(conn, "RANK_CHANGED", issue_id, None, actor, {"from": old_level, "to": issue["threat_level"]})
    return issue, changed


CLOSED_STATUSES = ("RESOLVED", "DISMISSED")


def dismiss_if_no_reports(conn, issue_id, actor, reason):
    """Close an issue as invalid once no valid report remains (e.g. all marked fake). Kept in the ledger, off the map."""
    row = conn.execute("SELECT status FROM issues WHERE id=?", (issue_id,)).fetchone()
    if not row or row["status"] in CLOSED_STATUSES:
        return False
    if conn.execute("SELECT 1 FROM reports WHERE issue_id=? AND status='ACTIVE' LIMIT 1", (issue_id,)).fetchone():
        return False
    conn.execute("UPDATE issues SET status='DISMISSED', resolved_at=?, verify_deadline=NULL WHERE id=?", (now_iso(), issue_id))
    write_block(conn, "DISMISSED", issue_id, None, actor, {"status": "DISMISSED", "reason": reason})
    return True


ESCALATION_STEP = 2  # severity and emergency each go up this much per failed repair (capped at 10)


def escalate(conn, issue_id, actor, reason):
    """A repair failed verification: raise severity/emergency, count the failed fix, and alert staff."""
    before = conn.execute("SELECT severity, threat_level FROM issues WHERE id=?", (issue_id,)).fetchone()
    conn.execute("UPDATE issues SET escalation = MIN(COALESCE(escalation, 0) + ?, 9),"
                 " failed_fix_attempts = failed_fix_attempts + 1 WHERE id=?", (ESCALATION_STEP, issue_id))
    issue, _ = recount(conn, issue_id, actor)
    write_block(conn, "ESCALATED", issue_id, None, actor, {
        "reason": reason, "severity_from": before["severity"], "severity_to": issue["severity"],
        "threat_level": issue["threat_level"], "failed_fix_attempts": issue["failed_fix_attempts"]})
    for email in STAFF_EMAILS:
        # TODO: email/SMS after the hackathon; the dashboard also updates live through the ledger stream.
        print(f"[notify] URGENT to {email}: {issue_id} repair failed verification ({reason}). "
              f"Severity {before['severity']} -> {issue['severity']} ({issue['threat_level']}). Immediate action required.",
              flush=True)
    return issue


def current_rank(conn, issue_id):
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM issues WHERE status IN ('OPEN','REOPENED','FIX_SUBMITTED','AWAITING_STUDENT_CHECK')"
        " ORDER BY priority DESC")]
    return ids.index(issue_id) + 1 if issue_id in ids else len(ids) + 1


def refresh_work_order(conn, issue_id):
    issue = dict(conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone())
    linked = [dict(r) for r in conn.execute(
        "SELECT issue_a, issue_b, note FROM issue_links WHERE issue_a=? OR issue_b=?", (issue_id, issue_id))]
    try:
        r = gemma.rank_and_work_order(issue, current_rank(conn, issue_id), linked)
    except gemma.GemmaError:
        return
    conn.execute(
        "UPDATE issues SET rank_reason=?, work_order_en=?, work_order_ml=?, trade_needed=? WHERE id=?",
        (r.get("rank_reason"), r.get("work_order_en"), r.get("work_order_ml"), r.get("trade_needed"), issue_id),
    )
