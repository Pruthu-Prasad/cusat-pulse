"""Issue queries and status changes shared by the routers and the other services."""
from datetime import datetime, timedelta, timezone

from core.database import get_db, now_iso, rows
from core.errors import AppError
from core.security import public_user
from services import antifake, ranking
from services.ledger import write_block

ACTIVE_STATUSES = ("OPEN", "REOPENED", "FIX_SUBMITTED", "AWAITING_STUDENT_CHECK")


# ---------- helpers used inside a DB transaction ----------

def get_issue_or_404(conn, issue_id):
    row = conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
    if not row:
        raise AppError(404, "Issue not found.")
    return dict(row)


def set_status(conn, issue_id, status, **fields):
    sets = ", ".join(["status=?"] + [f"{k}=?" for k in fields])
    conn.execute(f"UPDATE issues SET {sets} WHERE id=?", (status, *fields.values(), issue_id))


def issue_photos(conn, issue_id):
    reps = conn.execute(
        "SELECT image_path FROM reports WHERE issue_id=? AND status='ACTIVE' ORDER BY created_at, id", (issue_id,)).fetchall()
    return [r["image_path"] for r in reps]


def latest_fix_photo(conn, issue_id):
    row = conn.execute("SELECT image_path FROM audits WHERE issue_id=? AND kind='staff_fix' AND passed=1"
                       " ORDER BY id DESC LIMIT 1", (issue_id,)).fetchone()
    return row["image_path"] if row else None


def user_in_issue(conn, user_id, issue_id):
    return conn.execute("SELECT 1 FROM reports WHERE issue_id=? AND user_id=? AND status='ACTIVE'",
                        (issue_id, user_id)).fetchone() is not None


def resolve_issue(conn, issue_id, actor_name, reason):
    set_status(conn, issue_id, "RESOLVED", resolved_at=now_iso(), verify_deadline=None)
    write_block(conn, "RESOLVED", issue_id, None, actor_name, {"status": "RESOLVED", "reason": reason})


# ---------- reads ----------

def my_reports(user):
    with get_db() as conn:
        reps = rows(conn.execute(
            "SELECT r.id, r.issue_id, r.image_path, r.ai_description, r.category, r.severity, r.status AS report_status,"
            " r.created_at, i.title, i.status, i.threat_level, i.verify_deadline, i.unique_reporters, i.fix_disputed"
            " FROM reports r LEFT JOIN issues i ON i.id = r.issue_id WHERE r.user_id=? ORDER BY r.created_at DESC, r.id DESC",
            (user["id"],)))
        for r in reps:
            r["after_photo"] = latest_fix_photo(conn, r["issue_id"]) if r["issue_id"] else None
            r["already_confirmed"] = bool(r["issue_id"] and conn.execute(
                "SELECT 1 FROM audits WHERE issue_id=? AND user_id=? AND kind='student_confirm'"
                " AND created_at >= COALESCE((SELECT MAX(created_at) FROM audits WHERE issue_id=? AND kind='staff_fix'"
                " AND passed=1), '')", (r["issue_id"], user["id"], r["issue_id"])).fetchone())
    return {"user": public_user(user), "reports": reps}


def list_for_map(user, include_resolved):
    # Resolved issues leave the map (records stay in the ledger); staff can ask for recent ones on the heat map.
    if include_resolved and user["role"] in ("staff", "admin"):
        since = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        where, args = "status NOT IN ('RESOLVED','DISMISSED') OR (status='RESOLVED' AND resolved_at >= ?)", (since,)
    else:
        where, args = "status NOT IN ('RESOLVED','DISMISSED')", ()
    with get_db() as conn:
        out = rows(conn.execute(
            "SELECT id, title, category, building, floor, lat, lng, status, threat_level, severity, unique_reporters,"
            f" priority, fix_disputed, failed_fix_attempts, created_at FROM issues WHERE {where}"
            " ORDER BY priority DESC, id", args))
        links = rows(conn.execute("SELECT issue_a, issue_b, note FROM issue_links"))
    return {"issues": out, "links": links}


def detail(issue_id, user):
    staff = user["role"] in ("staff", "admin")
    with get_db() as conn:
        issue = get_issue_or_404(conn, issue_id)
        issue["breakdown"] = ranking.breakdown(issue)
        issue["rank"] = ranking.current_rank(conn, issue_id)
        reports = rows(conn.execute(
            "SELECT r.id, r.image_path, r.ai_description, r.advice, r.note, r.severity, r.emergency, r.complexity,"
            " r.confidence, r.hazard_box, r.merge_type, r.merge_reason, r.counts_toward_total, r.status, r.created_at,"
            " r.floor, r.lat, r.lng, r.gps_lat, r.gps_lng, u.name, u.cusat_id, u.trust_score"
            " FROM reports r JOIN users u ON u.id=r.user_id WHERE r.issue_id=? ORDER BY r.created_at, r.id", (issue_id,)))
        for r in reports:
            r["gps_flag"] = antifake.gps_flag(r["lat"], r["lng"], r.pop("gps_lat"), r.pop("gps_lng"))
        if not staff:
            for r in reports:
                for k in ("name", "cusat_id", "trust_score", "note", "gps_flag"):
                    r.pop(k, None)
            for k in ("work_order_en", "work_order_ml"):
                issue.pop(k, None)
        issue["reports"] = reports
        issue["audits"] = rows(conn.execute(
            "SELECT kind, image_path, same_location_verified, passed, reason, created_at FROM audits WHERE issue_id=?"
            " ORDER BY id", (issue_id,)))
        issue["after_photo"] = latest_fix_photo(conn, issue_id)
        issue["i_reported"] = user_in_issue(conn, user["id"], issue_id)
        issue["links"] = rows(conn.execute(
            "SELECT issue_a, issue_b, note FROM issue_links WHERE issue_a=? OR issue_b=?", (issue_id, issue_id)))
        if staff:
            issue["ledger"] = rows(conn.execute(
                "SELECT block_no, event, report_id, actor, block_hash, created_at FROM ledger WHERE issue_id=?"
                " ORDER BY block_no", (issue_id,)))
    return issue


def grouped():
    with get_db() as conn:
        issues = rows(conn.execute("SELECT * FROM issues ORDER BY severity DESC, priority DESC, id"))
        flagged = rows(conn.execute(
            "SELECT r.id, r.image_path, r.ai_description, r.building, r.created_at, r.lat, r.lng, r.gps_lat, r.gps_lng,"
            " u.name, u.cusat_id FROM reports r JOIN users u ON u.id=r.user_id WHERE r.status='FLAGGED'"
            " ORDER BY r.created_at DESC, r.id DESC"))
        for f in flagged:
            f["gps_flag"] = antifake.gps_flag(f["lat"], f["lng"], f.pop("gps_lat"), f.pop("gps_lng"))
    groups = {}
    for i in issues:
        groups.setdefault(i["category"], {}).setdefault(i["building"] or "Free pin", []).append(i)
    out = [{"category": cat, "count": sum(len(v) for v in locs.values()),
            "locations": [{"building": b, "issues": v} for b, v in locs.items()]}
           for cat, locs in groups.items()]
    out.sort(key=lambda g: -max(i["severity"] or 0 for loc in g["locations"] for i in loc["issues"]))
    top = sorted([i for i in issues if i["status"] in ACTIVE_STATUSES], key=lambda i: -(i["priority"] or 0))[:5]
    return {"groups": out, "top": top, "flagged": flagged}


def heatmap():
    with get_db() as conn:
        pts = rows(conn.execute("SELECT id, lat, lng, priority, category, threat_level, status FROM issues ORDER BY id"))
    for p in pts:
        p["weight"] = round((p["priority"] or 0) / 12, 3)
    return {"points": pts}
