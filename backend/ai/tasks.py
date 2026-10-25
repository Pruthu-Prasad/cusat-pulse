"""Every Gemma task the app performs. Services call these through the module (tasks.triage(...)),
so tests can swap any of them for a fixed answer."""
import json

from ai.client import GemmaError, call_json, generate_with_tools, img_part  # noqa: F401  (re-exported for services)
from ai.prompts import AUDIT_SYSTEM, DISPUTE_SYSTEM, FAKE_CHECK_SYSTEM, MATCH_SYSTEM, RANK_SYSTEM, TRIAGE_SYSTEM
from ai.schemas import AUDIT_SCHEMA, CATEGORIES, DISPUTE_SCHEMA, FAKE_CHECK_SCHEMA, MATCH_SCHEMA, RANK_SCHEMA, TRIAGE_SCHEMA


def _clamp(v, lo=1, hi=10):
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return lo


# ---------- 1. Triage ----------

def triage(image, note, building, floor):
    text = f"Location: {building or 'unknown building'}, floor {floor or 'unknown'}.\nStudent note: {note or '(none)'}"
    r = call_json("triage", TRIAGE_SYSTEM, [image], text, TRIAGE_SCHEMA)
    for k in ("severity", "emergency", "complexity"):
        r[k] = _clamp(r.get(k))
    if r.get("category") not in CATEGORIES:
        r["category"] = "Other"
    r["confidence"] = max(0.0, min(1.0, float(r.get("confidence") or 0)))
    r.setdefault("title", r.get("what_i_see", "Campus issue")[:60])
    if not note:
        r["text_matches_photo"] = True
    return r


# ---------- 2. Grouping fallback (the tool loop itself lives in services/grouping.py) ----------

def match_fallback(triage_result, candidates):
    text = json.dumps({"new_report": triage_result, "candidates": candidates})
    return call_json("match", MATCH_SYSTEM, [], text, MATCH_SCHEMA)


# ---------- 3. Fix audit ----------

def audit_fix(before, latest, after, note):
    return call_json("audit", AUDIT_SYSTEM, [before, latest, after], f"Staff note: {note or '(none)'}", AUDIT_SCHEMA)


# ---------- 4. Student verification / dispute ----------

def check_dispute(before, after, new):
    return call_json("dispute", DISPUTE_SYSTEM, [before, after, new], "Check the student's dispute.", DISPUTE_SCHEMA)


# ---------- 4b. Staff "this report is fake" check ----------

def check_fake_claim(report_photo, staff_photo, reported):
    return call_json("fake_check", FAKE_CHECK_SYSTEM, [report_photo, staff_photo],
                     f"The student reported: {reported or '(no description)'}", FAKE_CHECK_SCHEMA)


# ---------- 5. Rank reason + work order ----------

def rank_and_work_order(issue, rank, linked):
    text = json.dumps({
        "rank": rank,
        "title": issue["title"], "summary": issue["summary"], "category": issue["category"],
        "building": issue["building"], "floor": issue["floor"],
        "severity": issue["severity"], "emergency": issue["emergency"], "complexity": issue["complexity"],
        "threat_level": issue["threat_level"], "priority": issue["priority"],
        "unique_students": issue["unique_reporters"], "linked_issues": linked,
    })
    return call_json("rank", RANK_SYSTEM, [], text, RANK_SCHEMA, temperature=0.4)
