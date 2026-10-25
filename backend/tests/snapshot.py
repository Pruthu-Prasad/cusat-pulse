"""API contract snapshot: drives every endpoint through a full scenario and records status + JSON.

    python -m tests.snapshot record   # write tests/golden.json from the current code
    python -m tests.snapshot check    # run again and diff against tests/golden.json (exit 1 on any difference)

Runs on a throwaway database with Gemma replaced by fixed answers, so results are repeatable.
Timestamps, hashes, tokens, job ids and upload file names are normalised before comparing.
"""
import io
import json
import random
import re
import sys
import tempfile
from pathlib import Path

GOLDEN = Path(__file__).with_name("golden.json")


# ---------- point the app at a temp database (works before and after the refactor) ----------

def _setup():
    tmp = Path(tempfile.mkdtemp()) / "snapshot.db"
    try:
        from core import config, database as db  # new layout
        from ai import tasks as ai
        from scripts import seed_cusat
    except ImportError:
        import config, db  # noqa: E401  (old flat layout)
        import gemma as ai
        import seed_cusat
    config.DB_PATH = tmp
    db.DB_PATH = tmp
    return ai, seed_cusat


ai, seed_cusat = _setup()


# ---------- Gemma stubs ----------

class Stub:
    triage = None          # dict returned by the next triage call
    match = None           # dict returned by match_fallback
    audit = None
    dispute = None
    fake = None


def _triage(image, note, building, floor):
    t = dict(Stub.triage)
    if not note:
        t["text_matches_photo"] = True
    return t


def _no_tools(*_a, **_k):
    raise RuntimeError("tool loop disabled in snapshot; agent uses its fallback")


ai.triage = _triage
ai.generate_with_tools = _no_tools
ai.match_fallback = lambda t, candidates: dict(Stub.match)
ai.audit_fix = lambda before, latest, after, note: dict(Stub.audit)
ai.check_dispute = lambda before, after, new: dict(Stub.dispute)
ai.check_fake_claim = lambda report, staff, reported: dict(Stub.fake)
ai.rank_and_work_order = lambda issue, rank, linked: {
    "rank_reason": f"Ranked #{rank}: test", "work_order_en": "WO EN", "work_order_ml": "WO ML", "trade_needed": "Tester"}

TRIAGE_OK = {"is_valid_hazard": True, "what_i_see": "Exposed wires on a wall socket.", "title": "Exposed socket wires",
             "category": "Electrical", "severity": 8, "emergency": 7, "complexity": 3, "who_is_at_risk": "Students",
             "immediate_advice": "Keep away.", "confidence": 0.9, "hazard_box": [10, 10, 500, 500],
             "text_matches_photo": True, "likely_screen_photo": False, "likely_stock_or_web_image": False,
             "authenticity_note": ""}


# ---------- normalisation ----------

PATTERNS = [
    (re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"), "<TS>"),
    (re.compile(r"\b[0-9a-f]{64}\b"), "<HASH>"),
    (re.compile(r"\b[0-9a-f]{32}\.jpg\b"), "<IMG>.jpg"),
    (re.compile(r"JOB-[0-9a-f]{10}"), "<JOB>"),
    (re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+"), "<JWT>"),
]
VOLATILE_KEYS = {"token"}


def norm(v, key=None):
    if isinstance(v, dict):
        return {k: norm(x, k) for k, x in v.items()}
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, str):
        if key in VOLATILE_KEYS:
            return "<TOKEN>"
        for pat, rep in PATTERNS:
            v = pat.sub(rep, v)
        return v
    if isinstance(v, float):
        return round(v, 2)
    return v


def photo(seed):
    r = random.Random(seed)
    img = __import__("PIL.Image", fromlist=["Image"]).new("RGB", (640, 480), (r.randint(0, 255),) * 3)
    d = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(img)
    for _ in range(40):
        x, y = r.randint(0, 600), r.randint(0, 440)
        d.rectangle([x, y, x + r.randint(20, 220), y + r.randint(20, 220)], fill=tuple(r.randint(0, 255) for _ in range(3)))
    b = io.BytesIO()
    img.save(b, "JPEG")
    return b.getvalue()


# ---------- scenario ----------

def run():
    seed_cusat.seed()
    import main
    from fastapi.testclient import TestClient

    out = []
    with TestClient(main.app) as c:
        def rec(name, resp, stream=False):
            if stream:
                body = [json.loads(l[5:]) for l in resp.text.splitlines() if l.startswith("data:")]
            else:
                ct = resp.headers.get("content-type", "")
                body = resp.json() if "json" in ct else {"content_type": ct, "bytes": len(resp.content) > 0}
            out.append({"name": name, "status": resp.status_code, "body": norm(body)})
            return resp

        def login(email):
            c.post("/api/auth/request-otp", json={"email": email})
            r = c.post("/api/auth/verify-otp", json={"email": email, "code": "000000"})
            return {"Authorization": "Bearer " + r.json()["token"]}

        def tok(h):
            return c.post("/api/capture-token", headers=h).json()["token"]

        def report(h, name, img, building="CITTIC", floor="1", note="", lat=10.04101, lng=76.32825, token=None):
            data = {"capture_token": token or tok(h), "lat": lat, "lng": lng, "building": building, "floor": floor,
                    "gps_lat": lat, "gps_lng": lng}
            if note:
                data["note"] = note
            r = rec(name, c.post("/api/reports", headers=h, data=data, files={"image": ("p.jpg", img, "image/jpeg")}))
            if r.status_code == 200:
                rec(name + " /stream", c.get(f"/api/stream/{r.json()['job_id']}", headers=h), stream=True)
            return r

        def upload(path, h, img, extra=None, name=None):
            data = {"capture_token": tok(h), **(extra or {})}
            return rec(name or path, c.post(path, headers=h, data=data, files={"image": ("p.jpg", img, "image/jpeg")}))

        # --- auth ---
        rec("otp: wrong domain", c.post("/api/auth/request-otp", json={"email": "x@gmail.com"}))
        rec("otp: new user without profile", c.post("/api/auth/request-otp", json={"email": "newbie@cusat.ac.in"}))
        rec("otp: duplicate cusat id", c.post("/api/auth/request-otp", json={"email": "newbie@cusat.ac.in", "name": "N", "cusat_id": "cus 1001"}))
        rec("otp: new user ok", c.post("/api/auth/request-otp", json={"email": "newbie@cusat.ac.in", "name": "Newbie", "cusat_id": "NEW001"}))
        rec("verify: wrong code", c.post("/api/auth/verify-otp", json={"email": "newbie@cusat.ac.in", "code": "123"}))
        rec("verify: no otp requested", c.post("/api/auth/verify-otp", json={"email": "ghost@cusat.ac.in", "code": "000000"}))
        c.post("/api/auth/request-otp", json={"email": "demo1@cusat.ac.in"})
        rec("verify: demo ok", c.post("/api/auth/verify-otp", json={"email": "demo1@cusat.ac.in", "code": "000000"}))
        S1, S2, S3, S10 = (login(f"demo{n}@cusat.ac.in") for n in (1, 2, 3, 10))
        ST, AD = login("itsupport@cusat.ac.in"), login("estate@cusat.ac.in")

        # --- access control ---
        rec("issues: no token", c.get("/api/issues"))
        rec("issues: bad token", c.get("/api/issues", headers={"Authorization": "Bearer nope"}))
        rec("heatmap: student", c.get("/api/admin/heatmap", headers=S1))
        rec("grouped: student", c.get("/api/admin/issues/grouped", headers=S1))
        rec("ledger: staff", c.get("/api/ledger", headers=ST))
        rec("verify: staff", c.get("/api/ledger/verify", headers=ST))
        rec("seed: staff", c.post("/api/demo/seed", headers=ST))
        rec("accept: student", c.post("/api/admin/reports/RPT-0017/accept", headers=S1))

        # --- reads ---
        rec("me: demo1", c.get("/api/me", headers=S1))
        rec("me: admin", c.get("/api/me", headers=AD))
        rec("capture-token", c.post("/api/capture-token", headers=S1))
        rec("issues: student", c.get("/api/issues", headers=S1))
        rec("issues: student include_resolved", c.get("/api/issues?include_resolved=true", headers=S1))
        rec("issues: staff include_resolved", c.get("/api/issues?include_resolved=true", headers=AD))
        rec("issue: student CL-0001", c.get("/api/issues/CL-0001", headers=S1))
        rec("issue: staff CL-0001", c.get("/api/issues/CL-0001", headers=AD))
        rec("issue: 404", c.get("/api/issues/CL-9999", headers=S1))
        rec("grouped: staff", c.get("/api/admin/issues/grouped", headers=ST))
        rec("heatmap: staff", c.get("/api/admin/heatmap", headers=ST))

        # --- reporting ---
        Stub.triage = {**TRIAGE_OK, "is_valid_hazard": False, "what_i_see": "A clean wall."}
        report(S2, "report: not a hazard", photo(1))
        Stub.triage = {**TRIAGE_OK, "text_matches_photo": False}
        r = report(S2, "report: text mismatch", photo(2), note="water leaking everywhere")
        job = c.get(f"/api/stream/{r.json()['job_id']}", headers=S2)
        clar_job = json.loads([l for l in job.text.splitlines() if '"final"' in l][-1][5:])
        clar_job = json.loads(clar_job["text"])["job_id"]
        Stub.triage, Stub.match = dict(TRIAGE_OK), {"match_issue_id": "", "merge_type": "none", "reason": "nothing similar"}
        r = rec("clarify: go with photo", c.post(f"/api/reports/{clar_job}/clarify", headers=S2, json={"choice": "photo"}))
        rec("clarify /stream", c.get(f"/api/stream/{r.json()['job_id']}", headers=S2), stream=True)
        rec("clarify: expired job", c.post(f"/api/reports/{clar_job}/clarify", headers=S2, json={"choice": "photo"}))
        Stub.match = {"match_issue_id": "CL-0001", "merge_type": "same_object", "reason": "same box"}
        report(S10, "report: merge into CL-0001", photo(3), building="Sahara Hostel", floor="Ground",
               lat=10.04589, lng=76.32927)
        Stub.triage = {**TRIAGE_OK, "likely_screen_photo": True, "confidence": 0.95, "authenticity_note": "screen bezel"}
        report(S3, "report: flagged screen photo", photo(4))
        Stub.triage = dict(TRIAGE_OK)
        report(S3, "report: duplicate photo", photo(3))
        t = tok(S3)
        report(S3, "report: token first use", photo(5), token=t, building="SOE", floor="2", lat=10.04878, lng=76.33132)
        report(S3, "report: reused token", photo(6), token=t)
        rec("report: not an image", c.post("/api/reports", headers=S3, data={"capture_token": tok(S3), "lat": 1, "lng": 1},
                                           files={"image": ("x.jpg", b"not an image", "image/jpeg")}))
        rec("report: missing fields", c.post("/api/reports", headers=S3, data={}))

        # --- accept flagged as real ---
        Stub.match = {"match_issue_id": "", "merge_type": "none", "reason": "new"}
        r = rec("accept: flagged seed report", c.post("/api/admin/reports/RPT-0017/accept", headers=ST))
        rec("accept /stream", c.get(f"/api/stream/{r.json()['job_id']}", headers=ST), stream=True)
        rec("accept: again", c.post("/api/admin/reports/RPT-0017/accept", headers=ST))
        rec("accept: 404", c.post("/api/admin/reports/RPT-9999/accept", headers=ST))

        # --- repair + verification window on CL-0005 ---
        before = c.get("/api/issues/CL-0005", headers=ST).json()["reports"][0]["image_path"]
        before_bytes = c.get(f"/uploads/{before}", headers=ST).content
        upload("/api/admin/issues/CL-0005/fix", ST, before_bytes, {"note": "fixed"}, "fix: reused before photo")
        Stub.audit = {"same_location_verified": True, "resolved": True, "is_screen_or_reused": False, "reason": "repaired"}
        upload("/api/admin/issues/CL-0005/fix", ST, photo(10), {"note": "new socket"}, "fix: passes")
        upload("/api/admin/issues/CL-0005/fix", ST, photo(11), None, "fix: not waiting for a fix")
        rec("issue: awaiting check (student view)", c.get("/api/issues/CL-0005", headers=S10))
        Stub.dispute = {"same_location_verified": True, "problem_still_present": True, "is_screen_or_reused": False, "reason": "still broken"}
        upload("/api/issues/CL-0005/confirm", S10, photo(12), None, "confirm: photo shows problem -> reopen+escalate")
        rec("issue: after escalation", c.get("/api/issues/CL-0005", headers=AD))
        Stub.audit = {"same_location_verified": True, "resolved": False, "is_screen_or_reused": False, "reason": "not fixed"}
        upload("/api/admin/issues/CL-0005/fix", ST, photo(13), None, "fix: audit fails")
        Stub.audit = {"same_location_verified": True, "resolved": True, "is_screen_or_reused": False, "reason": "repaired"}
        upload("/api/admin/issues/CL-0005/fix", ST, photo(14), None, "fix: passes again")
        Stub.dispute = {"same_location_verified": True, "problem_still_present": False, "is_screen_or_reused": False, "reason": "looks fine"}
        upload("/api/issues/CL-0005/dispute", S10, photo(15), None, "dispute: false claim")
        Stub.dispute = {"same_location_verified": False, "problem_still_present": False, "is_screen_or_reused": False, "reason": "other room"}
        upload("/api/issues/CL-0005/confirm", S10, photo(16), None, "confirm: wrong place")
        upload("/api/issues/CL-0005/dispute", S10, before_bytes, None, "dispute: reused photo")
        Stub.dispute = {"same_location_verified": True, "problem_still_present": False, "is_screen_or_reused": False, "reason": "repaired"}
        upload("/api/issues/CL-0005/confirm", S10, photo(17), None, "confirm: verified -> resolved")
        upload("/api/issues/CL-0005/confirm", S10, photo(18), None, "confirm: no longer awaiting")
        rec("confirm: no photo", c.post("/api/issues/CL-0005/confirm", headers=S10))

        # --- mark fake (proof photo) + dismissal ---
        rid3 = c.get("/api/issues/CL-0003", headers=ST).json()["reports"][2]["id"]
        Stub.fake = {"same_location_verified": True, "problem_present": True, "is_screen_or_reused": False, "reason": "still dry"}
        upload(f"/api/admin/reports/{rid3}/mark-fake", ST, photo(20), None, "mark-fake: problem still visible")
        Stub.fake = {"same_location_verified": False, "problem_present": False, "is_screen_or_reused": False, "reason": "elsewhere"}
        upload(f"/api/admin/reports/{rid3}/mark-fake", ST, photo(21), None, "mark-fake: wrong place")
        Stub.fake = {"same_location_verified": True, "problem_present": False, "is_screen_or_reused": False, "reason": "spot fine"}
        upload(f"/api/admin/reports/{rid3}/mark-fake", ST, photo(22), None, "mark-fake: accepted")
        upload(f"/api/admin/reports/{rid3}/mark-fake", ST, photo(23), None, "mark-fake: already fake")
        rid4 = c.get("/api/issues/CL-0004", headers=ST).json()["reports"][0]["id"]
        upload(f"/api/admin/reports/{rid4}/mark-fake", ST, photo(24), None, "mark-fake: last report -> dismissed")
        rec("mark-fake: 404", c.post("/api/admin/reports/RPT-9999/mark-fake", headers=ST, data={"capture_token": tok(ST)},
                                     files={"image": ("p.jpg", photo(25), "image/jpeg")}))

        # --- final state ---
        rec("issues: student after", c.get("/api/issues", headers=S1))
        rec("issues: staff after", c.get("/api/issues?include_resolved=true", headers=AD))
        rec("grouped: after", c.get("/api/admin/issues/grouped", headers=AD))
        rec("heatmap: after", c.get("/api/admin/heatmap", headers=AD))
        for n, h in (("demo3", S3), ("demo10", S10)):
            rec(f"me: {n} after", c.get("/api/me", headers=h))
        for i in ("CL-0003", "CL-0004", "CL-0005", "CL-0007"):
            rec(f"issue: {i} after (staff)", c.get(f"/api/issues/{i}", headers=AD))

        # --- ledger, seed, uploads ---
        rec("ledger: page 1", c.get("/api/ledger", headers=AD))
        rec("ledger: page 2", c.get("/api/ledger?page=2", headers=AD))
        rec("ledger: filter", c.get("/api/ledger?issue_id=CL-0005", headers=AD))
        rec("ledger: verify", c.get("/api/ledger/verify", headers=AD))
        rec("seed: already seeded", c.post("/api/demo/seed", headers=AD))
        rec("upload: no token", c.get("/uploads/seed_sahara_1.jpg"))
        rec("upload: token in query", c.get("/uploads/seed_sahara_1.jpg?token=" + S1["Authorization"][7:]))
        rec("upload: missing", c.get("/uploads/nope.jpg", headers=S1))
        rec("upload: traversal", c.get("/uploads/..%2Fmain.py", headers=S1))
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    got = run()
    if mode == "record":
        GOLDEN.write_text(json.dumps(got, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        print(f"recorded {len(got)} calls -> {GOLDEN.name}")
        return 0
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    got = json.loads(json.dumps(got, ensure_ascii=False, sort_keys=True))
    bad = 0
    if len(want) != len(got):
        print(f"DIFF: {len(want)} calls recorded, {len(got)} now")
        bad += 1
    for w, g in zip(want, got):
        if w != g:
            bad += 1
            print(f"DIFF in '{w['name']}'  (status {w['status']} -> {g['status']})")
            print("   was:", json.dumps(w["body"], ensure_ascii=False)[:400])
            print("   now:", json.dumps(g["body"], ensure_ascii=False)[:400])
    print(f"{len(got) - bad}/{len(got)} calls identical" + ("" if bad else "  -- ALL MATCH"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
