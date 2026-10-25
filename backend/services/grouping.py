import json
from datetime import datetime, timedelta, timezone

from google.genai import types

from ai import tasks
from ai.prompts import AGENT_SYSTEM
from core.config import MERGE_RADIUS_METERS, REOPEN_WINDOW_HOURS, UPLOAD_DIR
from core.database import next_id, now_iso
from services.antifake import haversine_m
from services.ledger import write_block
from services.ranking import escalate, recount, threat_level

MAX_STEPS = 8
OPEN_STATUSES = ("OPEN", "REOPENED", "FIX_SUBMITTED", "AWAITING_STUDENT_CHECK")
# Issues that were marked fixed: a fresh report of the same problem reopens them instead of starting a new ticket.
FIXED_STATUSES = ("AWAITING_STUDENT_CHECK", "RESOLVED")

def _decl(name, description, props, required):
    return types.FunctionDeclaration(
        name=name, description=description,
        parameters={"type": "OBJECT", "properties": props, "required": required},
    )


S = {"type": "STRING"}
N = {"type": "NUMBER"}
TOOLS = [
    _decl("find_nearby_issues", "Up to 5 open issues in the same building (or within 50m) with descriptions.",
          {"building": S, "lat": N, "lng": N, "category": S}, ["building", "category"]),
    _decl("get_issue_photos", "The first and latest photo of an issue, with what each shows.",
          {"issue_id": S}, ["issue_id"]),
    _decl("merge_into_issue", "Link the new report to an existing issue.",
          {"issue_id": S, "merge_type": {"type": "STRING", "enum": ["same_object", "same_root_problem"]}, "reason": S},
          ["issue_id", "merge_type", "reason"]),
    _decl("create_issue", "Start a new issue at this report's location.",
          {"title": S, "category": S, "reason": S}, ["title", "category", "reason"]),
    _decl("link_related", "Mark two issues in different buildings as possibly connected, without merging.",
          {"issue_id_a": S, "issue_id_b": S, "note": S}, ["issue_id_a", "issue_id_b", "note"]),
    _decl("notify_department", "Write a work order note for the department.",
          {"category": S, "message": S}, ["category", "message"]),
]


def log_event(conn, job_id, kind, text):
    step = conn.execute("SELECT COUNT(*) c FROM agent_events WHERE report_id=?", (job_id,)).fetchone()["c"] + 1
    conn.execute("INSERT INTO agent_events (report_id, step, kind, text, created_at) VALUES (?,?,?,?,?)",
                 (job_id, step, kind, text, now_iso()))
    conn.commit()


class Grouper:
    """Runs the grouping tools for one new report. ctx holds the report fields and triage result."""

    def __init__(self, conn, job_id, ctx):
        self.conn, self.job_id, self.ctx = conn, job_id, ctx
        self.t = ctx["triage"]
        self.issue_id = None
        self.report_id = None
        self.merge_type = None
        self.level_changed = False
        self.reopened = False
        self.nudged = False  # create_issue is held back once if a recently fixed issue could be the same problem
        self.extra_parts = []

    # ----- hard rules -----

    def _same_place(self, issue):
        b = self.ctx["building"]
        if b:
            return issue["building"] == b
        if issue["building"]:
            return False
        return haversine_m(self.ctx["lat"], self.ctx["lng"], issue["lat"], issue["lng"]) <= MERGE_RADIUS_METERS

    def _since(self):
        return (datetime.now(timezone.utc) - timedelta(hours=REOPEN_WINDOW_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _mergeable(self, row):
        """Open issues, plus issues marked fixed within REOPEN_WINDOW_HOURS (merging into those reopens them)."""
        if row["status"] in OPEN_STATUSES:
            return True
        return row["status"] == "RESOLVED" and bool(row["resolved_at"]) and row["resolved_at"] >= self._since()

    def _candidates(self):
        q = (f"SELECT * FROM issues WHERE status IN ({','.join('?' * len(OPEN_STATUSES))})"
             " OR (status='RESOLVED' AND resolved_at >= ?)")
        out = [dict(r) for r in self.conn.execute(q, (*OPEN_STATUSES, self._since())) if self._same_place(r)]
        out.sort(key=lambda i: (i["category"] != self.t["category"], -(i["priority"] or 0)))
        return out[:5]

    # ----- tools -----

    def find_nearby_issues(self, **_):
        # Location comes from the report, not from the model, so it can't search another building.
        cands = self._candidates()
        found = [{"issue_id": i["id"], "title": i["title"], "category": i["category"], "floor": i["floor"],
                  "summary": i["summary"], "students": i["unique_reporters"], "status": i["status"],
                  "recently_fixed": i["status"] in FIXED_STATUSES} for i in cands]
        fixed = sum(1 for f in found if f["recently_fixed"])
        where = self.ctx["building"] or "this spot"
        extra = f" ({fixed} recently fixed)" if fixed else ""
        return {"issues": found}, f"find_nearby_issues({where}) -> {len(found)} issue{'s' if len(found) != 1 else ''}{extra}"

    def get_issue_photos(self, issue_id, **_):
        reps = self.conn.execute(
            "SELECT id, image_path, ai_description FROM reports WHERE issue_id=? AND status='ACTIVE' ORDER BY created_at, id",
            (issue_id,)).fetchall()
        if not reps:
            return {"error": "No such issue"}, f"get_issue_photos({issue_id}) -> not found"
        picks = [reps[0]] if len(reps) == 1 else [reps[0], reps[-1]]
        for r in picks:
            path = UPLOAD_DIR / r["image_path"]
            if path.exists():
                self.extra_parts.append(tasks.img_part(path.read_bytes()))
        return ({"note": f"The next {len(picks)} image(s) are this issue's first and latest photos.",
                 "photos": [{"report_id": r["id"], "shows": r["ai_description"]} for r in picks]},
                f"get_issue_photos({issue_id}) -> comparing")

    def merge_into_issue(self, issue_id, merge_type, reason="", **_):
        if self.issue_id:
            return {"error": f"Already placed in {self.issue_id}"}, "merge refused: already placed"
        row = self.conn.execute("SELECT * FROM issues WHERE id=?", (issue_id,)).fetchone()
        if not row or not self._mergeable(row):
            return {"error": "Issue is not open"}, f"merge_into_issue({issue_id}) -> refused, not open"
        if not self._same_place(row):
            return ({"error": "Different building. Never merge across buildings; use link_related or create_issue."},
                    f"merge_into_issue({issue_id}) -> refused, different building")
        if merge_type == "same_object" and row["floor"] and self.ctx["floor"] and row["floor"] != self.ctx["floor"]:
            return ({"error": "Different floor: same_object merges need the same floor."},
                    f"merge_into_issue({issue_id}) -> refused, different floor")
        if merge_type not in ("same_object", "same_root_problem"):
            merge_type = "same_root_problem"
        was = row["status"]
        self._insert_report(issue_id, merge_type, reason)
        if was in FIXED_STATUSES:
            # The problem is back after a "fix": reopen this issue and flag the fix, never a duplicate ticket.
            self.conn.execute("UPDATE issues SET status='REOPENED', fix_disputed=1, verify_deadline=NULL,"
                              " resolved_at=NULL WHERE id=?", (issue_id,))
            write_block(self.conn, "REOPENED", issue_id, self.report_id, self.ctx["actor"],
                        {"status": "REOPENED", "previous_status": was,
                         "reason": "A new report shows the problem again after it was marked fixed"})
            escalate(self.conn, issue_id, "gemma", "a new report shows the problem again after the repair")
            self.reopened = True
        issue, self.level_changed = recount(self.conn, issue_id, self.ctx["actor"])
        write_block(self.conn, "MERGED", issue_id, self.report_id, self.ctx["actor"],
                    {"merge_type": merge_type, "reason": reason, "unique_students": issue["unique_reporters"]})
        self.conn.commit()
        n = issue["unique_reporters"]
        tail = " -> REOPENED, fix flagged" if self.reopened else ""
        return ({"ok": True, "unique_students": n, "priority": issue["priority"], "reopened": self.reopened},
                f"merge_into_issue({issue_id}, {merge_type}) -> {n} student{'s' if n != 1 else ''}, priority {issue['priority']}{tail}")

    def create_issue(self, title=None, category=None, reason="", **_):
        if self.issue_id:
            return {"error": f"Already placed in {self.issue_id}"}, "create refused: already placed"
        if not self.nudged:
            self.nudged = True
            fixed = [i["id"] for i in self._candidates()
                     if i["status"] in FIXED_STATUSES and i["category"] == self.t["category"]]
            if fixed:
                return ({"error": f"Hold on: {', '.join(fixed)} was recently marked fixed in this same place with the same "
                                  "category. Use get_issue_photos to compare. If it is the same problem, call "
                                  "merge_into_issue (it will be reopened). Call create_issue again only if it is clearly different."},
                        f"create_issue -> held: checking recently fixed {', '.join(fixed)} first")
        t, c = self.t, self.ctx
        issue_id = next_id(self.conn, "issues", "CL")
        needs_check = t["confidence"] < 0.5 or c["trust_score"] < 50
        self.conn.execute(
            "INSERT INTO issues (id, title, category, building, floor, lat, lng, status, severity, emergency, complexity,"
            " threat_level, unique_reporters, priority, summary, needs_human_check, created_at)"
            " VALUES (?,?,?,?,?,?,?,'OPEN',?,?,?,?,1,0,?,?,?)",
            (issue_id, (title or t["title"])[:80], t["category"], c["building"], c["floor"], c["lat"], c["lng"],
             t["severity"], t["emergency"], t["complexity"], threat_level(t["severity"]), t["what_i_see"],
             int(needs_check), now_iso()),
        )
        write_block(self.conn, "ISSUE_CREATED", issue_id, None, c["actor"],
                    {"status": "OPEN", "title": title or t["title"], "category": t["category"], "reason": reason})
        self._insert_report(issue_id, "new", reason)
        issue, _ = recount(self.conn, issue_id, c["actor"])
        self.conn.commit()
        return ({"ok": True, "issue_id": issue_id, "priority": issue["priority"]},
                f"create_issue -> {issue_id}, priority {issue['priority']}")

    def link_related(self, issue_id_a, issue_id_b, note="", **_):
        ids = {r["id"] for r in self.conn.execute("SELECT id FROM issues WHERE id IN (?,?)", (issue_id_a, issue_id_b))}
        if issue_id_a == issue_id_b or len(ids) != 2:
            return {"error": "Need two different existing issues"}, "link_related -> refused"
        self.conn.execute("INSERT INTO issue_links (issue_a, issue_b, note, created_at) VALUES (?,?,?,?)",
                          (issue_id_a, issue_id_b, note, now_iso()))
        write_block(self.conn, "LINKED", issue_id_a, None, self.ctx["actor"], {"other": issue_id_b, "note": note})
        self.conn.commit()
        return {"ok": True}, f"link_related({issue_id_a}, {issue_id_b}) -> possibly connected"

    def notify_department(self, category=None, message="", **_):
        self.ctx["dept_message"] = message
        return {"ok": True}, f"notify_department({category or self.t['category']}) -> work order drafted"

    # ----- helpers -----

    def _insert_report(self, issue_id, merge_type, reason):
        c, t = self.ctx, self.t
        # A second report from the same student into the same issue is kept but does not count.
        repeat = self.conn.execute(
            "SELECT 1 FROM reports WHERE issue_id=? AND user_id=? AND counts_toward_total=1 AND status='ACTIVE'",
            (issue_id, c["user_id"])).fetchone()
        if c.get("existing_report_id"):
            # A flagged report staff accepted: place the row that already exists instead of adding one.
            self.report_id = c["existing_report_id"]
            self.conn.execute("UPDATE reports SET issue_id=?, merge_type=?, merge_reason=?, counts_toward_total=?,"
                              " status='ACTIVE' WHERE id=?",
                              (issue_id, merge_type, reason, 0 if repeat else 1, self.report_id))
            write_block(self.conn, "REPORT_CREATED", issue_id, self.report_id, c["actor"],
                        {"category": t["category"], "severity": t["severity"], "accepted_after_flag": True})
            self.issue_id, self.merge_type = issue_id, merge_type
            return
        self.report_id = next_id(self.conn, "reports", "RPT")
        self.conn.execute(
            "INSERT INTO reports (id, issue_id, user_id, image_path, image_phash, note, lat, lng, gps_lat, gps_lng,"
            " building, floor, ai_description, advice, category, severity, emergency, complexity, confidence, hazard_box,"
            " merge_type, merge_reason, counts_toward_total, status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'ACTIVE',?)",
            (self.report_id, issue_id, c["user_id"], c["image_path"], c["phash"], c["note"], c["lat"], c["lng"],
             c["gps_lat"], c["gps_lng"], c["building"], c["floor"], t["what_i_see"], t["immediate_advice"],
             t["category"], t["severity"], t["emergency"], t["complexity"], t["confidence"],
             json.dumps(t.get("hazard_box") or []), merge_type, reason, 0 if repeat else 1, now_iso()),
        )
        write_block(self.conn, "REPORT_CREATED", issue_id, self.report_id, c["actor"],
                    {"category": t["category"], "severity": t["severity"], "gps_flag": c.get("gps_flag")})
        self.issue_id, self.merge_type = issue_id, merge_type

    def execute(self, name, args):
        fn = getattr(self, name, None) if name in {d.name for d in TOOLS} else None
        if not fn:
            return {"error": f"Unknown tool {name}"}, f"{name} -> unknown tool"
        try:
            return fn(**args)
        except TypeError as e:
            return {"error": f"Bad arguments: {e}"}, f"{name} -> bad arguments"


def _one_line(text, limit=180):
    """The Agent Trace shows one readable line per step, even if the model rambles in markdown."""
    lines = [l.strip(" -*#>\t") for l in text.replace("**", "").replace("`", "").splitlines()]
    lines = [l for l in lines if l and not l.rstrip(":").lower().startswith(("analyze", "step", "the user wants"))]
    out = (lines[-1] if lines else text.strip())  # the last line is usually the conclusion
    return out if len(out) <= limit else out[:limit].rsplit(" ", 1)[0] + "..."


def run_agent(conn, job_id, ctx, image):
    g = Grouper(conn, job_id, ctx)
    t = ctx["triage"]
    intro = json.dumps({
        "new_report": {"title": t["title"], "category": t["category"], "what_i_see": t["what_i_see"],
                       "severity": t["severity"], "emergency": t["emergency"],
                       "building": ctx["building"], "floor": ctx["floor"], "lat": ctx["lat"], "lng": ctx["lng"],
                       "student_note": ctx["note"]},
    })
    contents = [types.Content(role="user", parts=[tasks.img_part(image), types.Part.from_text(text=intro)])]
    try:
        for _ in range(MAX_STEPS):
            log_event(conn, job_id, "thought", "Gemma is deciding the next step...")
            resp = tasks.generate_with_tools(AGENT_SYSTEM, contents, TOOLS)
            content = resp.candidates[0].content
            for p in content.parts or []:
                if p.text and p.text.strip() and not getattr(p, "thought", False):
                    log_event(conn, job_id, "thought", _one_line(p.text))
            calls = resp.function_calls or []
            if not calls:
                break
            contents.append(content)
            parts = []
            for fc in calls:
                args = dict(fc.args or {})
                result, summary = g.execute(fc.name, args)
                log_event(conn, job_id, "tool_call", summary)
                parts.append(types.Part.from_function_response(name=fc.name, response=result))
            parts += g.extra_parts
            g.extra_parts = []
            contents.append(types.Content(role="user", parts=parts))
    except Exception as e:  # loop misbehaves -> one compare call, still logged (plan's fallback)
        print(f"[agent] tool loop failed, using fallback: {e}", flush=True)
        if not g.issue_id:
            _fallback(conn, job_id, g)
    if not g.issue_id:
        g.nudged = True  # out of steps or the loop failed: don't hold the create back again
        _, summary = g.create_issue(t["title"], t["category"], "No matching open issue here.")
        log_event(conn, job_id, "tool_call", summary)
    return g


def _fallback(conn, job_id, g):
    found, summary = g.find_nearby_issues()
    log_event(conn, job_id, "tool_call", summary)
    if not found["issues"]:
        return
    try:
        m = tasks.match_fallback(g.t, found["issues"])
    except tasks.GemmaError:
        return
    if m.get("match_issue_id") and m.get("merge_type") in ("same_object", "same_root_problem"):
        log_event(conn, job_id, "thought", m.get("reason", ""))
        _, summary = g.merge_into_issue(m["match_issue_id"], m["merge_type"], m.get("reason", ""))
        log_event(conn, job_id, "tool_call", summary)
