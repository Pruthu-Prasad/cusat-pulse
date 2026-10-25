import io
import math
import secrets
from datetime import datetime, timedelta, timezone

import imagehash
from PIL import Image

from config import MAX_REPORTS_PER_HOUR
from db import parse_iso

PHASH_MAX_DISTANCE = 6
# Box around the CUSAT Thrikkakara campus (from OSM building extents, plus margin); GPS outside it only adds a flag.
CAMPUS_BOUNDS = (10.0385, 76.3225, 10.0510, 76.3340)


def phash(data):
    return str(imagehash.phash(Image.open(io.BytesIO(data))))


def find_duplicate_photo(conn, ph):
    h = imagehash.hex_to_hash(ph)
    for r in conn.execute("SELECT id, image_phash FROM reports WHERE image_phash IS NOT NULL"):
        if h - imagehash.hex_to_hash(r["image_phash"]) <= PHASH_MAX_DISTANCE:
            return r["id"]
    return None


def is_near_duplicate(ph, others):
    h = imagehash.hex_to_hash(ph)
    return any(o and h - imagehash.hex_to_hash(o) <= PHASH_MAX_DISTANCE for o in others)


def issue_capture_token(conn, user_id):
    token = secrets.token_urlsafe(24)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("INSERT INTO capture_tokens (token, user_id, expires_at) VALUES (?,?,?)", (token, user_id, expires))
    return token


def use_capture_token(conn, token, user_id):
    row = conn.execute("SELECT * FROM capture_tokens WHERE token=?", (token or "",)).fetchone()
    if not row or row["used"] or row["user_id"] != user_id or parse_iso(row["expires_at"]) < datetime.now(timezone.utc):
        return False
    conn.execute("UPDATE capture_tokens SET used=1 WHERE token=?", (token,))
    return True


def over_rate_limit(conn, user_id):
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    n = conn.execute("SELECT COUNT(*) c FROM reports WHERE user_id=? AND created_at >= ?", (user_id, since)).fetchone()["c"]
    return n >= MAX_REPORTS_PER_HOUR


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def gps_flag(lat, lng, gps_lat, gps_lng):
    if gps_lat is None or gps_lng is None:
        return "no_gps"
    s, w, n, e = CAMPUS_BOUNDS
    if not (s <= gps_lat <= n and w <= gps_lng <= e):
        return "outside_campus"
    if haversine_m(lat, lng, gps_lat, gps_lng) > 150:
        return "far_from_pin"
    return None


def adjust_trust(conn, user_id, delta):
    conn.execute("UPDATE users SET trust_score = MAX(0, MIN(100, trust_score + ?)) WHERE id=?", (delta, user_id))
