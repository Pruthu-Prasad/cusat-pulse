"""Photo uploads: validate, save under uploads/, load back."""
import io
import uuid

from PIL import Image

from core.config import UPLOAD_DIR
from core.errors import AppError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024


async def read_image(upload):
    data = await upload.read()
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise AppError(400, "The photo is empty or too large.")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
    except Exception:
        raise AppError(400, "That file is not a photo.")
    return data


def save_image(data):
    name = f"{uuid.uuid4().hex}.jpg"
    (UPLOAD_DIR / name).write_bytes(data)
    return name


def load_image(name):
    path = UPLOAD_DIR / (name or "")
    return path.read_bytes() if name and path.exists() else None


def upload_path(name):
    """Resolved path of an uploaded photo, or None if missing or outside uploads/ (no path traversal)."""
    path = (UPLOAD_DIR / name).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.exists():
        return None
    return path
