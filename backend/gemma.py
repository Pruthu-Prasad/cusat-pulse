import hashlib
import itertools
import json
import threading
import time

from google import genai
from google.genai import types

from config import DEMO_CACHE_PATH, DEMO_MODE, GEMINI_KEYS, GEMMA_MODEL

_keys = itertools.cycle(GEMINI_KEYS or [""])
_cache_lock = threading.Lock()


class GemmaError(Exception):
    pass


def next_client():
    key = next(_keys)
    if not key:
        raise GemmaError("No GEMINI_API_KEY set")
    return genai.Client(api_key=key)


def img_part(data):
    return types.Part.from_bytes(data=data, mime_type="image/jpeg")


# ---------- demo cache: every good answer is saved, used when the API fails in DEMO_MODE ----------

def _load_cache():
    try:
        return json.loads(DEMO_CACHE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _cache_key(kind, images, text):
    h = hashlib.sha256(kind.encode())
    for img in images:
        h.update(hashlib.sha256(img).digest())
    h.update((text or "").encode())
    return h.hexdigest()


def _cache_put(key, value):
    with _cache_lock:
        cache = _load_cache()
        cache[key] = value
        DEMO_CACHE_PATH.write_text(json.dumps(cache, indent=1), encoding="utf-8")


def _cache_get(key):
    return _load_cache().get(key)


def _is_rate_limit(e):
    return "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)


def with_retry(fn):
    delays = [1, 2, 4]
    for attempt in range(len(delays) + 1):
        try:
            return fn()
        except Exception as e:
            if attempt < len(delays) and (_is_rate_limit(e) or "503" in str(e) or "UNAVAILABLE" in str(e)):
                time.sleep(delays[attempt])
                continue
            raise


def _strip_fences(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


def call_json(kind, system, images, text, schema, temperature=0.2):
    """One structured Gemma call. Falls back to prompt-only JSON if the model rejects response_schema."""
    key = _cache_key(kind, images, text)
    contents = [img_part(i) for i in images] + [text]

    def schema_call():
        resp = next_client().models.generate_content(
            model=GEMMA_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=temperature,
            ),
        )
        return json.loads(_strip_fences(resp.text))

    def prompt_call():
        # TODO: only used if this model rejects JSON mode; the schema is put in the prompt instead.
        resp = next_client().models.generate_content(
            model=GEMMA_MODEL,
            contents=contents + [f"Reply with only one JSON object matching this schema, no other text:\n{json.dumps(schema)}"],
            config=types.GenerateContentConfig(system_instruction=system, temperature=temperature),
        )
        return json.loads(_strip_fences(resp.text))

    try:
        try:
            result = with_retry(schema_call)
        except Exception as e:
            if _is_rate_limit(e):
                raise
            result = with_retry(prompt_call)
        _cache_put(key, result)
        return result
    except Exception as e:
        cached = _cache_get(key) if DEMO_MODE else None
        if cached:
            return cached
        raise GemmaError(str(e)) from e


# ---------- 1. Triage ----------

TRIAGE_SYSTEM = """You are the safety inspector for CUSAT campus in Kochi. You look at one photo a
student took of a possible problem on campus, plus their optional note.
Describe only what you can see. Do not guess hidden causes.
Score severity (harm if ignored), emergency (how fast it gets worse) and
complexity (how hard to fix) from 1 to 10.
Give short safety advice a student can follow right now.
Check if the photo looks like a picture of a screen, a printout, a stock or
web image, or has a watermark. Check if the note matches the photo.
If there is no real problem in the photo, set is_valid_hazard to false and
say what you see instead, kindly.
Use plain, simple English."""

CATEGORIES = ["Electrical", "Plumbing", "Structural", "IT", "Sanitation", "Safety", "Other"]

TRIAGE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "is_valid_hazard": {"type": "BOOLEAN"},
        "what_i_see": {"type": "STRING"},
        "title": {"type": "STRING"},
        "category": {"type": "STRING", "enum": CATEGORIES},
        "severity": {"type": "INTEGER"},
        "emergency": {"type": "INTEGER"},
        "complexity": {"type": "INTEGER"},
        "who_is_at_risk": {"type": "STRING"},
        "immediate_advice": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
        "hazard_box": {"type": "ARRAY", "items": {"type": "INTEGER"}},
        "text_matches_photo": {"type": "BOOLEAN"},
        "likely_screen_photo": {"type": "BOOLEAN"},
        "likely_stock_or_web_image": {"type": "BOOLEAN"},
        "authenticity_note": {"type": "STRING"},
    },
    "required": ["is_valid_hazard", "what_i_see", "title", "category", "severity", "emergency", "complexity",
                 "immediate_advice", "confidence", "text_matches_photo", "likely_screen_photo",
                 "likely_stock_or_web_image"],
}


def _clamp(v, lo=1, hi=10):
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return lo


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


# ---------- 3. Fix audit ----------

AUDIT_SYSTEM = """You check repair work on CUSAT campus. You get photos in this order:
1) the first photo of the problem, 2) the latest student photo of the problem,
3) the photo staff took after the repair.
Decide if photo 3 shows the same place (judge walls, fixtures, signs and layout)
and if the problem in photos 1-2 is gone. Flag photo 3 if it looks like a photo of a
screen or printout, or is the same picture as photo 1 or 2. Give one plain sentence as reason."""

AUDIT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "same_location_verified": {"type": "BOOLEAN"},
        "resolved": {"type": "BOOLEAN"},
        "is_screen_or_reused": {"type": "BOOLEAN"},
        "reason": {"type": "STRING"},
    },
    "required": ["same_location_verified", "resolved", "is_screen_or_reused", "reason"],
}


def audit_fix(before, latest, after, note):
    return call_json("audit", AUDIT_SYSTEM, [before, latest, after], f"Staff note: {note or '(none)'}", AUDIT_SCHEMA)


# ---------- 4. Dispute check ----------

DISPUTE_SYSTEM = """A student says a repair on CUSAT campus did not work. You get photos in this order:
1) the first photo of the problem, 2) the photo staff took after the repair,
3) the student's new photo taken now.
Decide if photo 3 shows the same place and if the original problem is visible again.
Flag photo 3 if it looks like a photo of a screen or printout, or reuses photo 1.
Give one plain sentence as reason."""

DISPUTE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "same_location_verified": {"type": "BOOLEAN"},
        "problem_still_present": {"type": "BOOLEAN"},
        "is_screen_or_reused": {"type": "BOOLEAN"},
        "reason": {"type": "STRING"},
    },
    "required": ["same_location_verified", "problem_still_present", "is_screen_or_reused", "reason"],
}


def check_dispute(before, after, new):
    return call_json("dispute", DISPUTE_SYSTEM, [before, after, new], "Check the student's dispute.", DISPUTE_SCHEMA)


# ---------- 4b. Staff "this report is fake" check ----------

FAKE_CHECK_SYSTEM = """A student reported a problem on CUSAT campus. Staff say the report is false.
You get photos in this order: 1) the student's report photo, 2) the photo staff took just now at the reported spot.
Decide if photo 2 shows the same place as photo 1 (judge walls, fixtures, signs and layout),
and whether the reported problem is visible in photo 2.
Flag photo 2 if it looks like a photo of a screen or printout, or is the same picture as photo 1.
Give one plain sentence as reason."""

FAKE_CHECK_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "same_location_verified": {"type": "BOOLEAN"},
        "problem_present": {"type": "BOOLEAN"},
        "is_screen_or_reused": {"type": "BOOLEAN"},
        "reason": {"type": "STRING"},
    },
    "required": ["same_location_verified", "problem_present", "is_screen_or_reused", "reason"],
}


def check_fake_claim(report_photo, staff_photo, reported):
    return call_json("fake_check", FAKE_CHECK_SYSTEM, [report_photo, staff_photo],
                     f"The student reported: {reported or '(no description)'}", FAKE_CHECK_SCHEMA)


# ---------- 5. Rank reason + work order ----------

RANK_SYSTEM = """You write for the CUSAT estate and IT support teams.
Given one campus issue, write:
- rank_reason: one line starting "Ranked #N:" explaining why it has this priority.
- work_order_en: a short job card in English: what, where, likely tools or trade, risk level, safety note for the crew.
- work_order_ml: the same job card in Malayalam.
- trade_needed: one or two words, e.g. "Electrician".
Plain, short sentences."""

RANK_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "rank_reason": {"type": "STRING"},
        "work_order_en": {"type": "STRING"},
        "work_order_ml": {"type": "STRING"},
        "trade_needed": {"type": "STRING"},
    },
    "required": ["rank_reason", "work_order_en", "work_order_ml", "trade_needed"],
}


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


# ---------- 2. Grouping agent: raw generate with tools (loop lives in agent.py) ----------

def generate_with_tools(system, contents, tools):
    def call():
        return next_client().models.generate_content(
            model=GEMMA_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[types.Tool(function_declarations=tools)],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.1,
            ),
        )
    return with_retry(call)


MATCH_SYSTEM = """You decide if a new campus report is the same problem as one of the candidate issues.
same_object = the same physical thing. same_root_problem = same building, same category, one shared cause.
If none match, return an empty match_issue_id."""

MATCH_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "match_issue_id": {"type": "STRING"},
        "merge_type": {"type": "STRING", "enum": ["same_object", "same_root_problem", "none"]},
        "reason": {"type": "STRING"},
    },
    "required": ["match_issue_id", "merge_type", "reason"],
}


def match_fallback(triage_result, candidates):
    text = json.dumps({"new_report": triage_result, "candidates": candidates})
    return call_json("match", MATCH_SYSTEM, [], text, MATCH_SCHEMA)
