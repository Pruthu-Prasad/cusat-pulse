"""JSON response schemas Gemma must follow (passed as response_schema). Prompts live in ai/prompts.py."""

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

MATCH_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "match_issue_id": {"type": "STRING"},
        "merge_type": {"type": "STRING", "enum": ["same_object", "same_root_problem", "none"]},
        "reason": {"type": "STRING"},
    },
    "required": ["match_issue_id", "merge_type", "reason"],
}
