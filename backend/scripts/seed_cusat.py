"""Demo data. From backend/: `python -m scripts.seed_cusat --fresh` wipes and reseeds (the DB file is removed;
rows can't be deleted). Stop the backend first. Add --empty for logins only (no demo issues).

Real photos: drop JPEGs into seed_images/ named <photo key>.jpg (e.g. sahara_1.jpg). Missing ones get a placeholder.
Add --ai to run each real photo through Gemma (descriptions, scores, advice, rank reasons, EN/ML work orders)
instead of the canned text. Takes a few minutes; stop the backend first.
"""
import io
import json
import random
import sys
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw

from ai import tasks
from core.config import DB_PATH, SEED_IMAGE_DIR, STAFF_EMAILS, UPLOAD_DIR
from core.database import get_db, init_db, next_id, now_iso
from services import antifake, ranking
from services.ledger import write_block

# Coordinates from OpenStreetMap; names match frontend/src/buildings.js so grouping lines up.
PLACES = {
    "Sahara Hostel": (10.04589, 76.32927),
    "Athulya Hostel": (10.04455, 76.32384),
    "Aishwarya Hostel": (10.04394, 76.32384),
    "SOE": (10.04878, 76.33132),
    "CITTIC": (10.04101, 76.32825),
    "Amenity Centre": (10.04261, 76.32882),
}

STUDENTS = [("Anjali Menon", "CUS1001"), ("Rahul Nair", "CUS1002"), ("Fathima Rasheed", "CUS1003"),
            ("Arjun Pillai", "CUS1004"), ("Sneha Thomas", "CUS1005"), ("Vishnu Das", "CUS1006"),
            ("Aisha Kareem", "CUS1007"), ("Nikhil Varghese", "CUS1008"), ("Meera Krishnan", "CUS1009"),
            ("Joel Mathew", "CUS1010")]

SCENARIOS = [
    {
        "place": "Sahara Hostel", "floor": "Ground", "category": "Electrical", "hours_ago": 6,
        "title": "Sparking distribution box near the mess entrance",
        "summary": "Open distribution box with burnt, exposed wires and scorch marks; sparks reported.",
        "scores": (9, 9, 6), "students": [0, 1, 2], "merge": "same_object", "photos": ["sahara_1", "sahara_2", "sahara_3"],
        "desc": ["Open electrical box with exposed burnt wires.", "Same box from the left, scorch marks above the breaker.",
                 "Close-up of melted insulation inside the box."],
        "advice": "Don't touch it. Keep 2 m away and tell the warden to cut the mains.",
        "rank_reason": "Ranked #1: live electrical risk in a busy corridor; needs an electrician and the circuit isolated.",
        "trade": "Electrician",
        "wo_en": "WHAT: Sparking distribution box, exposed burnt wiring.\nWHERE: Sahara Hostel, ground floor, near mess entrance.\n"
                 "TRADE: Electrician (2), insulated tools, replacement MCBs.\nRISK: Critical.\nSAFETY: Isolate the mains before opening. Rubber gloves and mat.",
        "wo_ml": "എന്ത്: തീപ്പൊരി വരുന്ന ഡിസ്ട്രിബ്യൂഷൻ ബോക്സ്, കത്തിയ വയറുകൾ പുറത്ത്.\nഎവിടെ: സഹാറ ഹോസ്റ്റൽ, താഴത്തെ നില, മെസ്സിന് സമീപം.\n"
                 "ജോലിക്കാർ: ഇലക്ട്രീഷ്യൻ (2), ഇൻസുലേറ്റഡ് ഉപകരണങ്ങൾ.\nഅപകട നില: അതീവ ഗുരുതരം.\nസുരക്ഷ: തുറക്കുന്നതിന് മുമ്പ് മെയിൻ സ്വിച്ച് ഓഫ് ചെയ്യുക.",
    },
    {
        "place": "Athulya Hostel", "floor": "3+", "category": "Plumbing", "hours_ago": 14,
        "title": "No water on all floors since morning",
        "summary": "Several taps and showers across floors are dry; points to a supply or tank problem, not one tap.",
        "scores": (6, 7, 5), "students": [3, 4, 5, 6, 7, 8], "merge": "same_root_problem",
        "photos": ["athulya_1", "athulya_2", "athulya_3", "athulya_4", "athulya_5", "athulya_6"],
        "desc": ["Dry tap in a 3rd floor washroom.", "Shower with no water, 2nd floor.", "Empty bucket under a dry tap.",
                 "Dry wash basin row, 1st floor.", "Tap open with no flow.", "Overhead tank gauge reading empty."],
        "advice": "Store some drinking water and report to the warden. Don't leave taps open.",
        "rank_reason": "Ranked #2: whole building without water for 14 hours, six students affected; likely pump or tank fault.",
        "trade": "Plumber",
        "wo_en": "WHAT: No water supply on all floors.\nWHERE: Athulya Hostel, building-wide.\nTRADE: Plumber + pump operator; check tank, pump, main valve.\n"
                 "RISK: Medium-High (sanitation).\nSAFETY: Switch off the pump before inspecting.",
        "wo_ml": "എന്ത്: എല്ലാ നിലകളിലും വെള്ളമില്ല.\nഎവിടെ: അതുല്യ ഹോസ്റ്റൽ, മുഴുവൻ കെട്ടിടം.\nജോലിക്കാർ: പ്ലംബർ, പമ്പ് ഓപ്പറേറ്റർ; ടാങ്കും പമ്പും പരിശോധിക്കുക.\n"
                 "അപകട നില: ഇടത്തരം.\nസുരക്ഷ: പരിശോധിക്കുന്നതിന് മുമ്പ് പമ്പ് ഓഫ് ചെയ്യുക.",
    },
    {
        "place": "Aishwarya Hostel", "floor": "1", "category": "Plumbing", "hours_ago": 13,
        "title": "Taps dry in Aishwarya Hostel",
        "summary": "Dry taps in washrooms on two floors; started around the same time as Athulya Hostel next door.",
        "scores": (5, 6, 5), "students": [9, 0, 1], "merge": "same_root_problem", "photos": ["aishwarya_1", "aishwarya_2", "aishwarya_3"],
        "desc": ["Dry tap, 1st floor washroom.", "Shower with no water.", "Row of basins with no water."],
        "advice": "Store some drinking water and report to the warden.",
        "rank_reason": "Ranked #5: water failure for 3 students, possibly the same main supply as Athulya Hostel.",
        "trade": "Plumber",
        "wo_en": "WHAT: No water in washrooms.\nWHERE: Aishwarya Hostel, floors 1-2.\nTRADE: Plumber; check with the Athulya Hostel crew about the shared main line.\nRISK: Medium.\nSAFETY: Standard.",
        "wo_ml": "എന്ത്: ശുചിമുറികളിൽ വെള്ളമില്ല.\nഎവിടെ: ഐശ്വര്യ ഹോസ്റ്റൽ, 1-2 നിലകൾ.\nജോലിക്കാർ: പ്ലംബർ; അതുല്യ ഹോസ്റ്റലിലെ പ്രധാന ലൈനുമായി ഒത്തുനോക്കുക.\nഅപകട നില: ഇടത്തരം.",
    },
    {
        "place": "SOE", "floor": "2", "category": "Structural", "hours_ago": 20,
        "title": "Collapsed ceiling panel in a lab",
        "summary": "A false-ceiling panel has fallen onto a lab bench; the frame above is sagging.",
        "scores": (7, 6, 8), "students": [2], "merge": "new", "photos": ["soe_1"],
        "desc": ["Fallen ceiling panel on a lab bench, sagging frame above."],
        "advice": "Stay out from under the sagging section and keep the lab closed.",
        "rank_reason": "Ranked #3: more panels may fall in a room students use daily; needs a scaffold and a carpentry team.",
        "trade": "Carpenter",
        "wo_en": "WHAT: Collapsed false-ceiling panel, frame sagging.\nWHERE: SOE, 2nd floor lab.\nTRADE: Carpenter team + scaffold.\nRISK: High.\nSAFETY: Close the lab; hard hats.",
        "wo_ml": "എന്ത്: ഫാൾസ് സീലിംഗ് പാനൽ വീണു, ഫ്രെയിം താഴ്ന്നിരിക്കുന്നു.\nഎവിടെ: SOE, രണ്ടാം നില ലാബ്.\nജോലിക്കാർ: ആശാരി സംഘം, സ്കാഫോൾഡ്.\nഅപകട നില: ഉയർന്നത്.\nസുരക്ഷ: ലാബ് അടച്ചിടുക.",
    },
    {
        "place": "CITTIC", "floor": "1", "category": "IT", "hours_ago": 30,
        "title": "Projector not turning on in seminar hall",
        "summary": "Ceiling projector shows no power light; the rest of the hall works.",
        "scores": (2, 2, 3), "students": [4], "merge": "new", "photos": ["cittic_1"],
        "desc": ["Ceiling projector with no power light."],
        "advice": "No danger. Use the spare portable projector for now.",
        "rank_reason": "Ranked #6: no safety risk; schedule with IT support this week.",
        "trade": "IT technician",
        "wo_en": "WHAT: Projector dead.\nWHERE: CITTIC seminar hall, 1st floor.\nTRADE: IT technician; check power cable and lamp.\nRISK: Low.\nSAFETY: Use a ladder with a spotter.",
        "wo_ml": "എന്ത്: പ്രൊജക്ടർ പ്രവർത്തിക്കുന്നില്ല.\nഎവിടെ: CITTIC സെമിനാർ ഹാൾ.\nജോലിക്കാർ: ഐടി ടെക്നീഷ്യൻ.\nഅപകട നില: കുറവ്.",
    },
    {
        "place": "Amenity Centre", "floor": "Ground", "category": "Plumbing", "hours_ago": 8,
        "title": "Burst pipe flooding the corridor",
        "summary": "Water spraying from a cracked pipe joint at floor level; corridor floor is wet.",
        "scores": (7, 8, 6), "students": [5, 6], "merge": "same_object", "photos": ["amenity_1", "amenity_2"],
        "desc": ["Cracked pipe joint spraying water onto the floor.", "Same joint from the other side, puddle spreading."],
        "advice": "Walk around the wet area; it is slippery. Keep phones and chargers away.",
        "rank_reason": "Ranked #4: water is spreading in a busy corridor and wasting supply; slip risk.",
        "trade": "Plumber",
        "wo_en": "WHAT: Burst pipe joint.\nWHERE: Amenity Centre, ground floor corridor.\nTRADE: Plumber; replacement joint and clamps.\nRISK: High.\nSAFETY: Close the branch valve first; wet floor signs.",
        "wo_ml": "എന്ത്: പൈപ്പ് ജോയിന്റ് പൊട്ടി.\nഎവിടെ: അമിനിറ്റി സെന്റർ, താഴത്തെ നില ഇടനാഴി.\nജോലിക്കാർ: പ്ലംബർ.\nഅപകട നില: ഉയർന്നത്.\nസുരക്ഷ: ആദ്യം വാൽവ് അടയ്ക്കുക.",
    },
]

PALETTE = {"Electrical": (239, 68, 68), "Plumbing": (59, 130, 246), "Structural": (245, 158, 11), "IT": (168, 85, 247)}


def _photo_bytes(key, category, label):
    real = SEED_IMAGE_DIR / f"{key}.jpg"
    if real.exists():
        return real.read_bytes()
    rnd = random.Random(key)
    base = PALETTE.get(category, (107, 114, 128))
    img = Image.new("RGB", (960, 720), tuple(int(c * 0.35) for c in base))
    d = ImageDraw.Draw(img)
    # Random shapes so every placeholder has a distinct perceptual hash.
    for _ in range(40):
        x, y = rnd.randint(0, 900), rnd.randint(0, 680)
        w, h = rnd.randint(30, 300), rnd.randint(30, 300)
        shade = tuple(min(255, int(c * rnd.uniform(0.4, 1.3))) for c in base)
        d.rectangle([x, y, x + w, y + h], fill=shade)
    d.rectangle([0, 620, 960, 720], fill=(15, 23, 42))
    d.text((24, 640), f"DEMO PHOTO  {key}", fill=(255, 255, 255))
    d.text((24, 670), label[:110], fill=(203, 213, 225))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def _save_photo(key, category, label):
    data = _photo_bytes(key, category, label)
    name = f"seed_{key}.jpg"
    (UPLOAD_DIR / name).write_bytes(data)
    return name, antifake.phash(data)


USE_AI = False  # set by --ai: run real seed photos through Gemma instead of the canned text


def _ai_triage(key, s):
    """Gemma triage for a real seed photo (also fills the demo cache). None if off, no real photo, or Gemma fails."""
    real = SEED_IMAGE_DIR / f"{key}.jpg"
    if not USE_AI or not real.exists():
        return None
    try:
        t = tasks.triage(real.read_bytes(), "", s["place"], s["floor"])
    except tasks.GemmaError as e:
        print(f"  {key}: Gemma failed ({e}); using canned text", flush=True)
        return None
    if not t["is_valid_hazard"]:
        print(f"  {key}: Gemma says this photo shows no problem ({t['what_i_see'][:80]}); using canned text", flush=True)
        return None
    print(f"  {key}: {t['category']} severity {t['severity']} - {t['what_i_see'][:70]}", flush=True)
    return t


def _ago(hours):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _users(conn):
    ids = []
    for n, (name, cid) in enumerate(STUDENTS, start=1):
        email = f"demo{n}@cusat.ac.in"
        conn.execute("INSERT OR IGNORE INTO users (name, email, cusat_id, role, verified, created_at)"
                     " VALUES (?,?,?,'student',1,?)", (name, email, cid, now_iso()))
        ids.append(conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()["id"])
    for n, email in enumerate(STAFF_EMAILS):
        role = "admin" if n == 0 else "staff"
        conn.execute("INSERT OR IGNORE INTO users (name, email, cusat_id, role, verified, created_at)"
                     " VALUES (?,?,?,?,1,?)", (email.split("@")[0].title(), email, f"STAFF{n + 1}", role, now_iso()))
    return ids


def _scenario(conn, s, user_ids):
    lat, lng = PLACES[s["place"]]
    sev, em, cx = s["scores"]
    issue_id = next_id(conn, "issues", "CL")
    created = _ago(s["hours_ago"])
    conn.execute(
        "INSERT INTO issues (id, title, category, building, floor, lat, lng, status, severity, emergency, complexity,"
        " threat_level, unique_reporters, priority, summary, rank_reason, work_order_en, work_order_ml, trade_needed,"
        " created_at) VALUES (?,?,?,?,?,?,?,'OPEN',?,?,?,?,0,0,?,?,?,?,?,?)",
        (issue_id, s["title"], s["category"], s["place"], s["floor"], lat, lng, sev, em, cx, ranking.threat_level(sev),
         s["summary"], s["rank_reason"], s["wo_en"], s["wo_ml"], s["trade"], created))
    write_block(conn, "ISSUE_CREATED", issue_id, None, "seed", {"status": "OPEN", "title": s["title"]})
    for n, (student, key, desc) in enumerate(zip(s["students"], s["photos"], s["desc"])):
        photo, ph = _save_photo(key, s["category"], desc)
        advice, (r_sev, r_em, r_cx) = s["advice"], s["scores"]
        t = _ai_triage(key, s)
        if t:
            # Gemma's own words about the real photo; the category stays fixed so the demo scenarios still line up.
            desc, advice, r_sev, r_em, r_cx = t["what_i_see"], t["immediate_advice"], t["severity"], t["emergency"], t["complexity"]
            if n == 0:
                conn.execute("UPDATE issues SET title=?, summary=? WHERE id=?", (t["title"][:80], t["what_i_see"], issue_id))
        report_id = next_id(conn, "reports", "RPT")
        uid = user_ids[student]
        jitter = n * 0.00003
        merge = "new" if n == 0 else s["merge"]
        conn.execute(
            "INSERT INTO reports (id, issue_id, user_id, image_path, image_phash, lat, lng, gps_lat, gps_lng, building, floor,"
            " ai_description, advice, category, severity, emergency, complexity, confidence, hazard_box, merge_type,"
            " merge_reason, counts_toward_total, status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0.9,'[]',?,?,1,'ACTIVE',?)",
            (report_id, issue_id, uid, photo, ph, lat + jitter, lng - jitter, lat + jitter * 2, lng - jitter / 2,
             s["place"], s["floor"], desc, advice, s["category"], r_sev, r_em, r_cx, merge, "Seeded scenario",
             _ago(s["hours_ago"] - n * 0.5)))
        write_block(conn, "REPORT_CREATED", issue_id, report_id, f"student:{STUDENTS[student][1]}", {"category": s["category"]})
        if n:
            write_block(conn, "MERGED", issue_id, report_id, f"student:{STUDENTS[student][1]}", {"merge_type": merge})
    ranking.recount(conn, issue_id, "seed")
    return issue_id


def seed(with_issues=True):
    init_db()
    with get_db() as conn:
        user_ids = _users(conn)
        if not with_issues:
            # Clean slate for a live presentation: demo/staff logins only, no issues, empty ledger.
            return {"seeded": True, "issues": [], "logins": [f"demo{n}@cusat.ac.in" for n in range(1, 11)] + STAFF_EMAILS}
        if conn.execute("SELECT COUNT(*) c FROM issues").fetchone()["c"]:
            return {"seeded": False, "message": "Data already exists. Run `python -m scripts.seed_cusat --fresh` to start over."}
        ids = [_scenario(conn, s, user_ids) for s in SCENARIOS]
        hostel_a, hostel_b = ids[1], ids[2]
        note = "Both hostels lost water around the same time; could be the main supply."
        conn.execute("INSERT INTO issue_links (issue_a, issue_b, note, created_at) VALUES (?,?,?,?)",
                     (hostel_a, hostel_b, note, now_iso()))
        write_block(conn, "LINKED", hostel_a, None, "gemma", {"other": hostel_b, "note": note})

        # Scenario 8: stock image photographed off a laptop screen -> flagged, not ranked.
        photo, ph = _save_photo("fake_flood", "Other", "Stock photo of a flooded room shown on a laptop screen")
        report_id = next_id(conn, "reports", "RPT")
        conn.execute(
            "INSERT INTO reports (id, user_id, image_path, image_phash, lat, lng, building, ai_description, category,"
            " severity, emergency, complexity, confidence, merge_type, status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,'Plumbing',8,8,5,0.85,'new','FLAGGED',?)",
            (report_id, user_ids[7], photo, ph, *PLACES["SOE"], "SOE",
             "A flooded room shown on a laptop screen; screen bezel and moire lines visible.", _ago(1)))
        write_block(conn, "REPORT_REJECTED_FAKE", None, report_id, f"student:{STUDENTS[7][1]}",
                    {"why": "Photo of a laptop screen showing a stock image"})
        conn.execute("UPDATE users SET trust_score = 95 WHERE id=?", (user_ids[7],))

        if USE_AI:
            # Now that every issue exists, Gemma writes each rank reason (with the real #N) and the EN/ML work orders.
            for issue_id in ids:
                print(f"  {issue_id}: writing rank reason and work order...", flush=True)
                ranking.refresh_work_order(conn, issue_id)
    return {"seeded": True, "issues": ids, "flagged": [report_id],
            "logins": [f"demo{n}@cusat.ac.in" for n in range(1, 6)] + STAFF_EMAILS}


if __name__ == "__main__":
    USE_AI = "--ai" in sys.argv
    if "--fresh" in sys.argv:
        for suffix in ("", "-wal", "-shm"):
            p = DB_PATH.with_name(DB_PATH.name + suffix)
            if p.exists():
                p.unlink()
    print(json.dumps(seed(with_issues="--empty" not in sys.argv), indent=2, ensure_ascii=False))
