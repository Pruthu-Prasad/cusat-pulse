import asyncio
import io
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from PIL import Image
from pydantic import BaseModel

import antifake
import gemma
import ranking
from agent import log_event, run_agent
from auth import actor, current_user, public_user, request_otp, require_admin, require_staff, verify_otp
from config import DEMO_MODE, UPLOAD_DIR, VERIFY_WINDOW_MINUTES
from db import get_db, init_db, next_id, now_iso, rows
from ledger import verify as verify_chain
from ledger import write_block
from scheduler import scheduler_loop

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
ACTIVE = ("OPEN", "REOPENED", "FIX_SUBMITTED", "AWAITING_STUDENT_CHECK")
FLAG_CONFIDENCE = 0.7
PENDING = {}  # job_id -> (ctx, image) for reports waiting on a "which one did you mean?" answer


@asynccontextmanager
async def lifespan(_app):
    init_db()
    task = asyncio.create_task(scheduler_loop())
    yield
    task.cancel()


app = FastAPI(title="CUSAT-Pulse", lifespan=lifespan)


@app.exception_handler(Exception)
async def plain_errors(_request, exc):
    print(f"[error] {exc!r}", flush=True)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})


# ---------- helpers ----------

async def read_image(upload: UploadFile):
    data = await upload.read()
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "The photo is empty or too large.")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except Exception:
        raise HTTPException(400, "That file is not a photo.")
    return data


def save_image(data):
    name = f"{uuid.uuid4().hex}.jpg"
    (UPLOAD_DIR / name).write_bytes(data)
    return name


def load_image(name):
    path = UPLOAD_DIR / (name or "")
    return path.read_bytes() if name and path.exists() else None


def get_issue_or_404(conn, issue_id):
    row = conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Issue not found.")
    return dict(row)


def set_status(conn, issue_id, status, **fields):
    sets = ", ".join(["status=?"] + [f"{k}=?" for k in fields])
    conn.execute(f"UPDATE issues SET {sets} WHERE id=?", (status, *fields.values(), issue_id))


def issue_photos(conn, issue_id):
    reps = conn.execute(
        "SELECT image_path FROM reports WHERE issue_id=? AND status='ACTIVE' ORDER BY created_at", (issue_id,)).fetchall()
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


# ---------- auth ----------

class OtpRequest(BaseModel):
    email: str
    name: Optional[str] = None
    cusat_id: Optional[str] = None


class OtpVerify(BaseModel):
    email: str
    code: str


@app.post("/api/auth/request-otp")
def api_request_otp(body: OtpRequest):
    return request_otp(body.name, body.email, body.cusat_id)


@app.post("/api/auth/verify-otp")
def api_verify_otp(body: OtpVerify):
    return verify_otp(body.email, body.code)


@app.get("/api/me")
def api_me(user=Depends(current_user)):
    with get_db() as conn:
        reps = rows(conn.execute(
            "SELECT r.id, r.issue_id, r.image_path, r.ai_description, r.category, r.severity, r.status AS report_status,"
            " r.created_at, i.title, i.status, i.threat_level, i.verify_deadline, i.unique_reporters, i.fix_disputed"
            " FROM reports r LEFT JOIN issues i ON i.id = r.issue_id WHERE r.user_id=? ORDER BY r.created_at DESC",
            (user["id"],)))
        for r in reps:
            r["after_photo"] = latest_fix_photo(conn, r["issue_id"]) if r["issue_id"] else None
            r["already_confirmed"] = bool(r["issue_id"] and conn.execute(
                "SELECT 1 FROM audits WHERE issue_id=? AND user_id=? AND kind='student_confirm'"
                " AND created_at >= COALESCE((SELECT MAX(created_at) FROM audits WHERE issue_id=? AND kind='staff_fix'"
                " AND passed=1), '')", (r["issue_id"], user["id"], r["issue_id"])).fetchone())
    return {"user": public_user(user), "reports": reps}


@app.post("/api/capture-token")
def api_capture_token(user=Depends(current_user)):
    with get_db() as conn:
        return {"token": antifake.issue_capture_token(conn, user["id"]), "expires_in": 120}


# ---------- reporting ----------

def process_report(job_id, ctx, image, skip_text_check=False):
    with get_db() as conn:
        try:
            log_event(conn, job_id, "thought", "Looking at photo...")
            t = gemma.triage(image, ctx["note"], ctx["building"], ctx["floor"])
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
        except gemma.GemmaError as e:
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


@app.post("/api/reports")
async def api_create_report(
    background: BackgroundTasks,
    image: UploadFile = File(...),
    capture_token: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    gps_lat: Optional[float] = Form(None),
    gps_lng: Optional[float] = Form(None),
    building: Optional[str] = Form(None),
    floor: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    user=Depends(current_user),
):
    data = await read_image(image)
    note = (note or "").strip()[:300]
    with get_db() as conn:
        if antifake.over_rate_limit(conn, user["id"]):
            raise HTTPException(429, "You've sent a lot of reports this hour. Please try again later.")
        if not antifake.use_capture_token(conn, capture_token, user["id"]):
            raise HTTPException(400, "Please take the photo again with the in-app camera.")
        ph = antifake.phash(data)
        dup = antifake.find_duplicate_photo(conn, ph)
        if dup:
            write_block(conn, "REPORT_REJECTED_FAKE", None, None, actor(user), {"duplicate_of": dup})
            conn.commit()
            raise HTTPException(409, f"This photo was already reported as {dup}.")
    ctx = {
        "user_id": user["id"], "actor": actor(user), "trust_score": user["trust_score"],
        "image_path": save_image(data), "phash": ph, "note": note,
        "lat": lat, "lng": lng, "gps_lat": gps_lat, "gps_lng": gps_lng,
        "building": (building or "").strip() or None, "floor": (floor or "").strip() or None,
        "gps_flag": antifake.gps_flag(lat, lng, gps_lat, gps_lng),
    }
    job_id = "JOB-" + uuid.uuid4().hex[:10]
    background.add_task(process_report, job_id, ctx, data)
    return {"job_id": job_id}


class Clarify(BaseModel):
    choice: str  # "photo" = go with what the photo shows


@app.post("/api/reports/{job_id}/clarify")
def api_clarify(job_id: str, body: Clarify, background: BackgroundTasks, user=Depends(current_user)):
    pending = PENDING.pop(job_id, None)
    if not pending or pending[0]["user_id"] != user["id"]:
        raise HTTPException(404, "This report has expired. Please start again.")
    ctx, image = pending
    if body.choice == "photo":
        ctx["note"] = ""
    new_job = "JOB-" + uuid.uuid4().hex[:10]
    background.add_task(process_report, new_job, ctx, image, True)
    return {"job_id": new_job}


async def sse(gen):
    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/stream/dashboard")
async def api_stream_dashboard(user=Depends(require_staff)):
    async def gen():
        last, idle = None, 0
        yield ": connected\n\n"  # flush headers now so the browser marks the stream open
        # End after ~5 minutes; EventSource reconnects by itself, and a finite stream lets the server reload/shut down.
        while idle < 600:
            with get_db() as conn:
                row = conn.execute("SELECT block_no, event, issue_id FROM ledger ORDER BY block_no DESC LIMIT 1").fetchone()
            cur = dict(row) if row else {"block_no": 0}
            if cur["block_no"] != (last or {}).get("block_no"):
                if last is not None:
                    yield f"data: {json.dumps(cur)}\n\n"
                last, idle = cur, 0
            idle += 1
            if idle % 20 == 0:
                yield ": ping\n\n"
            await asyncio.sleep(0.5)
    return await sse(gen())


@app.get("/api/stream/{job_id}")
async def api_stream_job(job_id: str, user=Depends(current_user)):
    async def gen():
        last_id, ticks = 0, 0
        yield ": connected\n\n"
        while ticks < 600:  # 5 minutes max
            with get_db() as conn:
                evs = rows(conn.execute("SELECT id, step, kind, text FROM agent_events WHERE report_id=? AND id>? ORDER BY id",
                                        (job_id, last_id)))
            for e in evs:
                last_id = e["id"]
                yield f"data: {json.dumps(e)}\n\n"
                if e["kind"] in ("final", "error"):
                    return
            ticks += 1
            if ticks % 20 == 0:
                yield ": ping\n\n"
            await asyncio.sleep(0.5)
    return await sse(gen())


# ---------- issues ----------

@app.get("/api/issues")
def api_issues(include_resolved: bool = False, user=Depends(current_user)):
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
            " ORDER BY priority DESC", args))
        links = rows(conn.execute("SELECT issue_a, issue_b, note FROM issue_links"))
    return {"issues": out, "links": links}


@app.get("/api/issues/{issue_id}")
def api_issue(issue_id: str, user=Depends(current_user)):
    staff = user["role"] in ("staff", "admin")
    with get_db() as conn:
        issue = get_issue_or_404(conn, issue_id)
        issue["breakdown"] = ranking.breakdown(issue)
        issue["rank"] = ranking.current_rank(conn, issue_id)
        reports = rows(conn.execute(
            "SELECT r.id, r.image_path, r.ai_description, r.advice, r.note, r.severity, r.emergency, r.complexity,"
            " r.confidence, r.hazard_box, r.merge_type, r.merge_reason, r.counts_toward_total, r.status, r.created_at,"
            " r.floor, r.lat, r.lng, r.gps_lat, r.gps_lng, u.name, u.cusat_id, u.trust_score"
            " FROM reports r JOIN users u ON u.id=r.user_id WHERE r.issue_id=? ORDER BY r.created_at", (issue_id,)))
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


@app.get("/api/admin/issues/grouped")
def api_grouped(user=Depends(require_staff)):
    with get_db() as conn:
        issues = rows(conn.execute("SELECT * FROM issues ORDER BY severity DESC, priority DESC"))
        flagged = rows(conn.execute(
            "SELECT r.id, r.image_path, r.ai_description, r.building, r.created_at, r.lat, r.lng, r.gps_lat, r.gps_lng,"
            " u.name, u.cusat_id FROM reports r JOIN users u ON u.id=r.user_id WHERE r.status='FLAGGED'"
            " ORDER BY r.created_at DESC"))
        for f in flagged:
            f["gps_flag"] = antifake.gps_flag(f["lat"], f["lng"], f.pop("gps_lat"), f.pop("gps_lng"))
    groups = {}
    for i in issues:
        groups.setdefault(i["category"], {}).setdefault(i["building"] or "Free pin", []).append(i)
    out = [{"category": cat, "count": sum(len(v) for v in locs.values()),
            "locations": [{"building": b, "issues": v} for b, v in locs.items()]}
           for cat, locs in groups.items()]
    out.sort(key=lambda g: -max(i["severity"] or 0 for loc in g["locations"] for i in loc["issues"]))
    top = sorted([i for i in issues if i["status"] in ACTIVE], key=lambda i: -(i["priority"] or 0))[:5]
    return {"groups": out, "top": top, "flagged": flagged}


@app.get("/api/admin/heatmap")
def api_heatmap(user=Depends(require_staff)):
    with get_db() as conn:
        pts = rows(conn.execute("SELECT id, lat, lng, priority, category, threat_level, status FROM issues"))
    for p in pts:
        p["weight"] = round((p["priority"] or 0) / 12, 3)
    return {"points": pts}


@app.post("/api/admin/issues/{issue_id}/fix")
async def api_fix(issue_id: str, image: UploadFile = File(...), capture_token: str = Form(...),
                  note: Optional[str] = Form(None), user=Depends(require_staff)):
    data = await read_image(image)
    with get_db() as conn:
        issue = get_issue_or_404(conn, issue_id)
        if issue["status"] not in ("OPEN", "REOPENED"):
            raise HTTPException(400, "This issue is not waiting for a fix.")
        if not antifake.use_capture_token(conn, capture_token, user["id"]):
            raise HTTPException(400, "Please take the photo again with the in-app camera.")
        conn.commit()
        photos = issue_photos(conn, issue_id)
        ph = antifake.phash(data)
        before_hashes = [r["image_phash"] for r in conn.execute(
            "SELECT image_phash FROM reports WHERE issue_id=?", (issue_id,))]

    # Gemma runs outside the DB transaction; nothing is written until we have a verdict.
    if antifake.is_near_duplicate(ph, before_hashes):
        result = {"same_location_verified": True, "resolved": False, "is_screen_or_reused": True,
                  "reason": "This is the same photo as the original report, not a photo of the repair."}
    else:
        before, latest = load_image(photos[0]), load_image(photos[-1])
        try:
            result = await asyncio.to_thread(gemma.audit_fix, before, latest, data, note)
        except gemma.GemmaError:
            raise HTTPException(503, "Gemma is busy right now. Please try again in a minute.")
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
        except gemma.GemmaError as e:
            print(f"[gemma] {e}", flush=True)
            log_event(conn, job_id, "error", "Gemma is busy right now. The report is accepted; try grouping again in a minute.")
        except Exception as e:
            print(f"[accept] {e!r}", flush=True)
            log_event(conn, job_id, "error", "Something went wrong while grouping this report.")


@app.post("/api/admin/reports/{report_id}/accept")
def api_accept_flagged(report_id: str, background: BackgroundTasks, user=Depends(require_staff)):
    with get_db() as conn:
        r = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Report not found.")
        if r["status"] != "FLAGGED":
            raise HTTPException(400, "This report is not waiting for a decision.")
        # Claim it now so a double click can't group it twice; the agent fills in issue_id.
        conn.execute("UPDATE reports SET status='ACTIVE' WHERE id=?", (report_id,))
        antifake.adjust_trust(conn, r["user_id"], +5)  # undo the authenticity penalty
        write_block(conn, "FLAG_CLEARED_BY_STAFF", None, report_id, actor(user), {})
    job_id = "JOB-" + uuid.uuid4().hex[:10]
    background.add_task(process_accept, job_id, report_id, actor(user))
    return {"job_id": job_id}


@app.post("/api/admin/reports/{report_id}/mark-fake")
async def api_mark_fake(report_id: str, image: UploadFile = File(...), capture_token: str = Form(...),
                        user=Depends(require_staff)):
    """Staff can only call a report fake with proof: a fresh photo of the same spot with no problem in it."""
    data = await read_image(image)
    with get_db() as conn:
        r = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if not r:
            raise HTTPException(404, "Report not found.")
        r = dict(r)
        if r["status"] == "MARKED_FAKE":
            return {"marked_fake": True, "reason": "Already marked as fake."}
        if not antifake.use_capture_token(conn, capture_token, user["id"]):
            raise HTTPException(400, "Please take the photo again with the in-app camera.")
        conn.commit()

    report_photo = load_image(r["image_path"])
    ph = antifake.phash(data)
    if antifake.is_near_duplicate(ph, [r["image_phash"]]):
        result = {"same_location_verified": True, "problem_present": True, "is_screen_or_reused": True,
                  "reason": "This is the student's own photo, not a new photo of the spot."}
    elif not report_photo:
        raise HTTPException(400, "The original report photo is missing, so this can't be checked.")
    else:
        try:
            result = await asyncio.to_thread(gemma.check_fake_claim, report_photo, data, r["ai_description"])
        except gemma.GemmaError:
            raise HTTPException(503, "Gemma is busy right now. Please try again in a minute.")
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


async def student_check(issue_id, image, capture_token, user, claim, background):
    """Verification window after a repair: any student photographs the spot and Gemma's evidence decides.

    Problem gone -> resolved now. Problem still there -> same issue reopened and escalated (whatever was claimed:
    the real problem wins). Wrong place / reused photo -> rejected; a false "still broken" costs trust.
    """
    data = await read_image(image)
    with get_db() as conn:
        issue = get_issue_or_404(conn, issue_id)
        if issue["status"] != "AWAITING_STUDENT_CHECK":
            raise HTTPException(400, "This issue is no longer awaiting verification.")
        if not antifake.use_capture_token(conn, capture_token, user["id"]):
            raise HTTPException(400, "Please take the photo again with the in-app camera.")
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
            result = await asyncio.to_thread(gemma.check_dispute, load_image(before_name), load_image(after_name), data)
        except gemma.GemmaError:
            raise HTTPException(503, "Gemma is busy right now. Please try again in a minute.")
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


@app.post("/api/issues/{issue_id}/confirm")
async def api_confirm(issue_id: str, background: BackgroundTasks, image: UploadFile = File(...),
                      capture_token: str = Form(...), user=Depends(current_user)):
    return await student_check(issue_id, image, capture_token, user, "resolved", background)


@app.post("/api/issues/{issue_id}/dispute")
async def api_dispute(issue_id: str, background: BackgroundTasks, image: UploadFile = File(...),
                      capture_token: str = Form(...), user=Depends(current_user)):
    return await student_check(issue_id, image, capture_token, user, "unresolved", background)


# ---------- ledger ----------

@app.get("/api/ledger")
def api_ledger(issue_id: Optional[str] = None, page: int = 1, user=Depends(require_admin)):
    size = 50
    with get_db() as conn:
        where, args = ("WHERE issue_id=?", [issue_id]) if issue_id else ("", [])
        blocks = rows(conn.execute(
            f"SELECT block_no, event, issue_id, report_id, actor, prev_hash, block_hash, created_at FROM ledger {where}"
            " ORDER BY block_no DESC LIMIT ? OFFSET ?", (*args, size, (page - 1) * size)))
        total = conn.execute(f"SELECT COUNT(*) c FROM ledger {where}", args).fetchone()["c"]
        latest = conn.execute("SELECT block_hash FROM ledger ORDER BY block_no DESC LIMIT 1").fetchone()
    return {"blocks": blocks, "total": total, "latest_hash": latest["block_hash"] if latest else None}


@app.get("/api/ledger/verify")
def api_ledger_verify(user=Depends(require_admin)):
    with get_db() as conn:
        return verify_chain(conn)


@app.post("/api/demo/seed")
def api_seed(user=Depends(require_admin)):
    if not DEMO_MODE:
        raise HTTPException(403, "Seeding is only allowed in demo mode.")
    import seed_cusat
    return seed_cusat.seed()


@app.get("/uploads/{name}")
def api_upload(name: str, user=Depends(current_user)):
    path = (UPLOAD_DIR / name).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.exists():
        raise HTTPException(404, "Photo not found.")
    return FileResponse(path, media_type="image/jpeg")

