"""Gemma connection: API keys, retries, the demo cache, and the two raw call shapes (JSON and tool calling)."""
import hashlib
import itertools
import json
import threading
import time

from google import genai
from google.genai import types

from core.config import DEMO_CACHE_PATH, DEMO_MODE, GEMINI_KEYS, GEMMA_MODEL

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


def generate_with_tools(system, contents, tools):
    """Raw tool-calling turn for the grouping agent (the loop lives in services/grouping.py)."""
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
