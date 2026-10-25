"""Student report pipeline: checks -> Gemma triage -> grouping agent -> rank/work order, streamed to the Agent Trace.
Also handles the 'which one did you mean?' clarification and staff accepting a flagged photo as real."""
import json
import uuid

from ai import tasks
from core.database import get_db, next_id, now_iso
from core.errors import AppError
from core.security import actor
from services import antifake, ranking
from services.grouping import log_event, run_agent
from services.ledger import write_block
from services.storage import load_image, save_image

FLAG_CONFIDENCE = 0.7
PENDING = {}  # job_id -> (ctx, image) for reports waiting on a "which one did you mean?" answer


def new_job_id():
    return "JOB-" + uuid.uuid4().hex[:10]


# ---------- entry points (called by routers) ----------

def submit_report(user, data, background, *, capture_token, lat, lng, gps_lat, gps_lng, building, floor, note):
    note = (note or "").strip()[:300]
    with get_db() as conn:
        if antifake.over_rate_limit(conn, user["id"]):
            raise AppError(429, "You've sent a lot of reports this hour. Please try again later.")
        if not antifake.use_capture_token(conn, capture_token, user["id"]):
            raise AppError(400, "Please take the photo again with the in-app camera.")
        ph = antifake.phash(data)
        dup = antifake.find_duplicate_photo(conn, ph)
        if dup:
            write_block(conn, "REPORT_REJECTED_FAKE", None, None, actor(user), {"duplicate_of": dup})
            conn.commit()
            raise AppError(409, f"This photo was already reported as {dup}.")
    ctx = {
        "user_id": user["id"], "actor": actor(user), "trust_score": user["trust_score"],
        "image_path": save_image(data), "phash": ph, "note": note,
        "lat": lat, "lng": lng, "gps_lat": gps_lat, "gps_lng": gps_lng,
        "building": (building or "").strip() or None, "floor": (floor or "").strip() or None,
        "gps_flag": antifake.gps_flag(lat, lng, gps_lat, gps_lng),
    }
    job_id = new_job_id()
    background.add_task(process_report, job_id, ctx, data)
    return {"job_id": job_id}


def clarify(job_id, choice, user, background):
    pending = PENDING.pop(job_id, None)
    if not pending or pending[0]["user_id"] != user["id"]:
        raise AppError(404, "This report has expired. Please start again.")
    ctx, image = pending
    if choice == "photo":
        ctx["note"] = ""
    new_job = new_job_id()
    background.add_task(process_report, new_job, ctx, image, True)
    return {"job_id": new_job}


def accept_flagged(report_id, user, background):
    with get_db() as conn:
        r = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if not r:
            raise AppError(404, "Report not found.")
        if r["status"] != "FLAGGED":
            raise AppError(400, "This report is not waiting for a decision.")
        # Claim it now so a double click can't group it twice; the agent fills in issue_id.
        conn.execute("UPDATE reports SET status='ACTIVE' WHERE id=?", (report_id,))
        antifake.adjust_trust(conn, r["user_id"], +5)  # undo the authenticity penalty
        write_block(conn, "FLAG_CLEARED_BY_STAFF", None, report_id, actor(user), {})
    job_id = new_job_id()
    background.add_task(process_accept, job_id, report_id, actor(user))
    return {"job_id": job_id}


# ---------- background jobs ----------

def process_report(job_id, ctx, image, skip_text_check=False):
    with get_db() as conn:
        try:
            log_event(conn, job_id, "thought", "Looking at photo...")
            t = tasks.triage(image, ctx["note"], ctx["building"], ctx["floor"])
            level = ranking.threat_level(t["severity"])
            log_event(conn, job_id, "thought", f"{t['category']}: {t['what_i_see']} Severity {t['severity']} ({level})")

            if not t["is_valid_hazard"]:
                log_event(conn, job_id, "final", json.dumps({"outcome": "not_hazard", "message": t["what_i_see"]}))
                return
            if not skip_text_check and not t.get("text_matches_photo", True):
                PENDING[job_id] = (ctx, image)
                log_event(conn, job_id, "final", json.dumps({
                    "outcome": "clarify", "job_id": job_id, "photo_shows": t["what_i_see"], "note": ctx["note"]}))
                return

            ctx["triage"] = t
            suspicious = (t.get("likely_screen_photo") or t.get("likely_stock_or_web_image")) and t["confidence"] > FLAG_CONFIDENCE
            if suspicious:
                save_flagged(conn, job_id, ctx, t)
                return
            if t.get("likely_screen_photo") or t.get("likely_stock_or_web_image"):
                antifake.adjust_trust(conn, ctx["user_id"], -5)

            place_report(conn, job_id, ctx, image)
        except tasks.GemmaError as e:
            print(f"[gemma] {e}", flush=True)
            msg = ("The server has no Gemini API key set. Ask the team to add it." if "No GEMINI_API_KEY" in str(e)
                   else "Gemma is busy right now. Please try again in a minute.")
            log_event(conn, job_id, "error", msg)
        except Exception as e:
            print(f"[pipeline] {e!r}", flush=True)
            log_event(conn, job_id, "error", "Something went wrong while saving your report. Please try again.")


def place_report(conn, job_id, ctx, image):
    """Grouping agent, then rank reason / work order if needed, then the final event for the Agent Trace."""
    t = ctx["triage"]
    g = run_agent(conn, job_id, ctx, image)
    issue = dict(conn.execute("SELECT * FROM issues WHERE id=?", (g.issue_id,)).fetchone())
    if g.merge_type == "new" or g.level_changed or issue["rank_reason"] is None:
        log_event(conn, job_id, "thought", "Writing rank reason and work order (English + Malayalam)...")
        ranking.refresh_work_order(conn, g.issue_id)
        issue = dict(conn.execute("SELECT * FROM issues WHERE id=?", (g.issue_id,)).fetchone())
    log_event(conn, job_id, "final", json.dumps({
        "outcome": "saved", "report_id": g.report_id, "issue_id": g.issue_id, "merge_type": g.merge_type,
        "reopened": g.reopened,
        "unique_students": issue["unique_reporters"], "priority": issue["priority"],
        "category": t["category"], "threat_level": issue["threat_level"], "severity": t["severity"],
        "what_i_see": t["what_i_see"], "advice": t["immediate_advice"],
        "who_is_at_risk": t.get("who_is_at_risk"), "needs_human_check": bool(issue["needs_human_check"]),
        "rank_reason": issue["rank_reason"],
    }))


def save_flagged(conn, job_id, ctx, t):
    report_id = next_id(conn, "reports", "RPT")
    conn.execute(
        "INSERT INTO reports (id, user_id, image_path, image_phash, note, lat, lng, gps_lat, gps_lng, building, floor,"
        " ai_description, advice, category, severity, emergency, complexity, confidence, merge_type, status, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'new','FLAGGED',?)",
        (report_id, ctx["user_id"], ctx["image_path"], ctx["phash"], ctx["note"], ctx["lat"], ctx["lng"],
         ctx["gps_lat"], ctx["gps_lng"], ctx["building"], ctx["floor"], t["what_i_see"], t["immediate_advice"],
         t["category"], t["severity"], t["emergency"], t["complexity"], t["confidence"], now_iso()))
    antifake.adjust_trust(conn, ctx["user_id"], -5)
    write_block(conn, "REPORT_REJECTED_FAKE", None, report_id, ctx["actor"],
                {"why": t.get("authenticity_note") or "Looks like a screen or web image"})
    log_event(conn, job_id, "thought", f"Authenticity check: {t.get('authenticity_note') or 'looks like a screen or web image'}")
    log_event(conn, job_id, "final", json.dumps({
        "outcome": "flagged", "report_id": report_id,
        "message": "We could not verify this photo. Please take it again on the spot."}))


def process_accept(job_id, report_id, staff_actor):
    """A flagged photo that staff say is genuine goes through the normal grouping agent, reusing its report row."""
    with get_db() as conn:
        try:
            r = dict(conn.execute("SELECT r.*, u.cusat_id, u.role, u.trust_score FROM reports r JOIN users u ON u.id=r.user_id"
                                  " WHERE r.id=?", (report_id,)).fetchone())
            log_event(conn, job_id, "thought", f"Staff ({staff_actor}) confirmed {report_id} shows a real problem. Grouping it now...")
            image = load_image(r["image_path"])
            if not image:
                log_event(conn, job_id, "error", "The photo for this report is missing.")
                return
            desc = r["ai_description"] or "Campus issue"
            t = {"title": desc.split(".")[0][:80], "category": r["category"] or "Other", "what_i_see": desc,
                 "severity": r["severity"] or 1, "emergency": r["emergency"] or 1, "complexity": r["complexity"] or 1,
                 "confidence": r["confidence"] or 0.5, "immediate_advice": r["advice"] or "Keep a safe distance.",
                 "hazard_box": json.loads(r["hazard_box"] or "[]")}
            ctx = {"user_id": r["user_id"], "actor": f"{r['role']}:{r['cusat_id']}", "trust_score": r["trust_score"],
                   "image_path": r["image_path"], "phash": r["image_phash"], "note": r["note"] or "",
                   "lat": r["lat"], "lng": r["lng"], "gps_lat": r["gps_lat"], "gps_lng": r["gps_lng"],
                   "building": r["building"], "floor": r["floor"], "existing_report_id": report_id, "triage": t}
            place_report(conn, job_id, ctx, image)
        except tasks.GemmaError as e:
            print(f"[gemma] {e}", flush=True)
            log_event(conn, job_id, "error", "Gemma is busy right now. The report is accepted; try grouping again in a minute.")
        except Exception as e:
            print(f"[accept] {e!r}", flush=True)
            log_event(conn, job_id, "error", "Something went wrong while grouping this report.")
