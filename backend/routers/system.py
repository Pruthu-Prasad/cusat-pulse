from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from core.config import DEMO_MODE
from core.errors import AppError
from core.security import current_user, require_admin
from schemas.ledger import SeedResult
from scripts import seed_cusat
from services.storage import upload_path

router = APIRouter(tags=["system"])


@router.post("/api/demo/seed", response_model=SeedResult, response_model_exclude_unset=True)
def api_seed(user=Depends(require_admin)):
    if not DEMO_MODE:
        raise AppError(403, "Seeding is only allowed in demo mode.")
    return seed_cusat.seed()


@router.get("/uploads/{name}")
def api_upload(name: str, user=Depends(current_user)):
    """Photos need a signed-in user (token in the header or ?token= for <img> tags)."""
    path = upload_path(name)
    if not path:
        raise AppError(404, "Photo not found.")
    return FileResponse(path, media_type="image/jpeg")
