"""Everything decided by comparing photos: staff repair audits, staff 'mark as fake' proof, and the student
verification window after a repair. Gemma runs outside DB transactions; nothing is written until there's a verdict."""
import asyncio
from datetime import datetime, timedelta, timezone

from ai import tasks
from core.config import VERIFY_WINDOW_MINUTES
from core.database import get_db, now_iso
from core.errors import AppError
from core.security import actor
from services import antifake, ranking
from services.issues import get_issue_or_404, issue_photos, latest_fix_photo, resolve_issue, set_status
from services.ledger import write_block
from services.storage import load_image, save_image


# ---------- staff submits a repair photo ----------

async def submit_fix(issue_id, data, capture_token, note, user):
    with get_db() as conn:
        issue = get_issue_or_404(conn, issue_id)
        if issue["status"] not in ("OPEN", "REOPENED"):
            raise AppError(400, "This issue is not waiting for a fix.")
        if not antifake.use_capture_token(conn, capture_token, user["id"]):
            raise AppError(400, "Please take the photo again with the in-app camera.")
        conn.commit()
        photos = issue_photos(conn, issue_id)
        ph = antifake.phash(data)
        before_hashes = [r["image_phash"] for r in conn.execute(
            "SELECT image_phash FROM reports WHERE issue_id=?", (issue_id,))]

    if antifake.is_near_duplicate(ph, before_hashes):
        result = {"same_location_verified": True, "resolved": False, "is_screen_or_reused": True,
                  "reason": "This is the same photo as the original report, not a photo of the repair."}
    else:
        before, latest = load_image(photos[0]), load_image(photos[-1])
        try:
            result = await asyncio.to_thread(tasks.audit_fix, before, latest, data, note)
        except tasks.GemmaError:
            raise AppError(503, "Gemma is busy right now. Please try again in a minute.")
    passed = bool(result.get("same_location_verified") and result.get("resolved") and not result.get("is_screen_or_reused"))

    with get_db() as conn:
        name = save_image(data)
        a = actor(user)
        prior = issue["status"]
        write_block(conn, "FIX_SUBMITTED", issue_id, None, a, {"status": "FIX_SUBMITTED", "note": note})
        conn.execute("INSERT INTO audits (issue_id, kind, user_id, image_path, image_phash, same_location_verified,"
                     " passed, reason, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (issue_id, "staff_fix", user["id"], name, ph, int(bool(result.get("same_location_verified"))),
                      int(passed), result.get("reason"), now_iso()))
        if passed:
            deadline = (datetime.now(timezone.utc) + timedelta(minutes=VERIFY_WINDOW_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
            set_status(conn, issue_id, "AWAITING_STUDENT_CHECK", verify_deadline=deadline)
            write_block(conn, "AUDIT_PASSED", issue_id, None, "gemma",
                        {"status": "AWAITING_STUDENT_CHECK", "reason": result.get("reason"), "deadline": deadline})
            for r in conn.execute("SELECT DISTINCT u.email FROM reports r JOIN users u ON u.id=r.user_id"
                                  " WHERE r.issue_id=? AND r.status='ACTIVE'", (issue_id,)):
                # TODO: email via SMTP; console only for the hackathon.
                print(f"[notify] {r['email']}: Staff marked {issue_id} as fixed. Please check before {deadline}.", flush=True)
        else:
            set_status(conn, issue_id, prior, failed_fix_attempts=issue["failed_fix_attempts"] + 1)
            write_block(conn, "AUDIT_FAILED", issue_id, None, "gemma", {"status": prior, "reason": result.get("reason")})
    return {"passed": passed, **result}


# ---------- staff marks a report as fake (needs a proof photo) ----------

async def mark_fake(report_id, data, capture_token, user):
    """Staff can only call a report fake with proof: a fresh photo of the same spot with no problem in it."""
    with get_db() as conn:
        r = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if not r:
            raise AppError(404, "Report not found.")
        r = dict(r)
        if r["status"] == "MARKED_FAKE":
            return {"marked_fake": True, "reason": "Already marked as fake."}
        if not antifake.use_capture_token(conn, capture_token, user["id"]):
            raise AppError(400, "Please take the photo again with the in-app camera.")
        conn.commit()

    report_photo = load_image(r["image_path"])
    ph = antifake.phash(data)
    if antifake.is_near_duplicate(ph, [r["image_phash"]]):
        result = {"same_location_verified": True, "problem_present": True, "is_screen_or_reused": True,
                  "reason": "This is the student's own photo, not a new photo of the spot."}
    elif not report_photo:
        raise AppError(400, "The original report photo is missing, so this can't be checked.")
    else:
        try:
            result = await asyncio.to_thread(tasks.check_fake_claim, report_photo, data, r["ai_description"])
        except tasks.GemmaError:
            raise AppError(503, "Gemma is busy right now. Please try again in a minute.")
    marked = bool(result.get("same_location_verified") and not result.get("problem_present")
                  and not result.get("is_screen_or_reused"))
    if marked:
        reason = result.get("reason")
    elif not result.get("same_location_verified"):
        reason = f"Not marked fake: this doesn't look like the reported spot. {result.get('reason', '')}"
    elif result.get("is_screen_or_reused"):
        reason = f"Not marked fake: the proof photo looks reused or taken off a screen. {result.get('reason', '')}"
    else:
        reason = f"Not marked fake: Gemma can still see the problem at this spot. {result.get('reason', '')}"

    with get_db() as conn:
        name = save_image(data)
        a = actor(user)
        conn.execute("INSERT INTO audits (issue_id, kind, user_id, image_path, image_phash, same_location_verified,"
                     " passed, reason, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (r["issue_id"], "staff_fake_check", user["id"], name, ph,
                      int(bool(result.get("same_location_verified"))), int(marked), result.get("reason"), now_iso()))
        if marked:
            conn.execute("UPDATE reports SET status='MARKED_FAKE', counts_toward_total=0 WHERE id=?", (report_id,))
            antifake.adjust_trust(conn, r["user_id"], -30)
            write_block(conn, "MARKED_FAKE_BY_STAFF", r["issue_id"], report_id, a,
                        {"proof_photo": name, "reason": result.get("reason")})
            if r["issue_id"]:
                ranking.recount(conn, r["issue_id"], a)
                if ranking.dismiss_if_no_reports(conn, r["issue_id"], a,
                                                 "Every report on this issue was marked fake by staff, with photo proof"):
                    reason = f"{reason} No valid reports remain, so {r['issue_id']} has been dismissed and removed from the map."
        else:
            # Refused claims are recorded too, so staff can't quietly retry until one sticks.
            write_block(conn, "FAKE_CLAIM_REJECTED", r["issue_id"], report_id, "gemma",
                        {"by": a, "proof_photo": name, "reason": result.get("reason")})
    return {"marked_fake": marked, "reason": reason, **{k: result.get(k) for k in
            ("same_location_verified", "problem_present", "is_screen_or_reused")}}


# ---------- student verification window after a repair ----------

async def student_check(issue_id, data, capture_token, user, claim, background):
    """Verification window after a repair: any student photographs the spot and Gemma's evidence decides.

    Problem gone -> resolved now. Problem still there -> same issue reopened and escalated (whatever was claimed:
    the real problem wins). Wrong place / reused photo -> rejected; a false "still broken" costs trust.
    """
    with get_db() as conn:
        issue = get_issue_or_404(conn, issue_id)
        if issue["status"] != "AWAITING_STUDENT_CHECK":
            raise AppError(400, "This issue is no longer awaiting verification.")
        if not antifake.use_capture_token(conn, capture_token, user["id"]):
            raise AppError(400, "Please take the photo again with the in-app camera.")
        conn.commit()
        before_name = issue_photos(conn, issue_id)[0]
        after_name = latest_fix_photo(conn, issue_id)
        known_hashes = [r["image_phash"] for r in conn.execute(
            "SELECT image_phash FROM reports WHERE issue_id=? UNION ALL"
            " SELECT image_phash FROM audits WHERE issue_id=? AND image_phash IS NOT NULL", (issue_id, issue_id))]

    ph = antifake.phash(data)
    if antifake.is_near_duplicate(ph, known_hashes):
        result = {"same_location_verified": True, "problem_still_present": False, "is_screen_or_reused": True,
                  "reason": "This photo was already submitted for this issue. Please take a new photo of the location."}
    else:
        try:
            problem = f"{issue['title']}. {issue['summary'] or ''}".strip()
            result = await asyncio.to_thread(tasks.check_dispute, load_image(before_name), load_image(after_name),
                                             data, problem)
        except tasks.GemmaError:
            raise AppError(503, "Gemma is busy right now. Please try again in a minute.")
    valid = bool(result.get("same_location_verified") and not result.get("is_screen_or_reused"))
    still_broken = valid and bool(result.get("problem_still_present"))
    outcome = "unresolved" if still_broken else "resolved" if valid else "rejected"

    with get_db() as conn:
        name = save_image(data)
        a = actor(user)
        kind = "student_confirm" if claim == "resolved" else "student_dispute"
        conn.execute("INSERT INTO audits (issue_id, kind, user_id, image_path, image_phash, same_location_verified,"
                     " passed, reason, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                     (issue_id, kind, user["id"], name, ph, int(bool(result.get("same_location_verified"))),
                      int(outcome == claim), result.get("reason"), now_iso()))
        if outcome == "resolved" and claim == "resolved":
            write_block(conn, "STUDENT_CONFIRMED", issue_id, None, a, {"photo": name, "reason": result.get("reason")})
            resolve_issue(conn, issue_id, a, "Repair verified by a student photo")
            message = f"Thank you. Your photo verifies the repair, so {issue_id} is now closed."
        elif outcome == "unresolved":
            write_block(conn, "DISPUTE_VERIFIED", issue_id, None, "gemma", {"by": a, "photo": name, "reason": result.get("reason")})
            set_status(conn, issue_id, "REOPENED", fix_disputed=1, verify_deadline=None, resolved_at=None)
            write_block(conn, "REOPENED", issue_id, None, a, {"status": "REOPENED"})
            ranking.escalate(conn, issue_id, "gemma", "a student photo shows the problem after the repair")
            background.add_task(refresh_work_order_bg, issue_id)
            message = (f"Your photo shows the problem is still there. {issue_id} has been reopened and escalated to "
                       "maintenance for immediate action.")
        elif outcome == "resolved":  # claimed still broken, but the photo shows it repaired
            antifake.adjust_trust(conn, user["id"], -10)
            write_block(conn, "DISPUTE_REJECTED", issue_id, None, "gemma", {"by": a, "reason": result.get("reason")})
            message = f"Not verified: the photo shows the repair in place. {result.get('reason', '')}"
        else:
            if claim == "unresolved":
                antifake.adjust_trust(conn, user["id"], -10)
            write_block(conn, "DISPUTE_REJECTED" if claim == "unresolved" else "CONFIRMATION_REJECTED", issue_id, None,
                        "gemma", {"by": a, "reason": result.get("reason")})
            message = f"Not verified: {result.get('reason', 'the photo could not be matched to this location.')}"
    return {"outcome": outcome, "claim": claim, "accepted": outcome == claim, "message": message,
            "reason": result.get("reason"),
            # kept for older clients
            "verified": outcome == "unresolved"}


def refresh_work_order_bg(issue_id):
    with get_db() as conn:
        ranking.refresh_work_order(conn, issue_id)
