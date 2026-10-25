from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile

from core.security import current_user
from schemas.reports import ClarifyRequest, JobOut
from services import reporting
from services.storage import read_image

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("", response_model=JobOut, response_model_exclude_unset=True)
async def api_create_report(
    background: BackgroundTasks,
    image: UploadFile = File(...),
    capture_token: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    gps_lat: Optional[float] = Form(None),
    gps_lng: Optional[float] = Form(None),
    building: Optional[str] = Form(None),
    floor: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    user=Depends(current_user),
):
    """Starts the Gemma pipeline in the background; follow it on /api/stream/{job_id}."""
    data = await read_image(image)
    return reporting.submit_report(user, data, background, capture_token=capture_token, lat=lat, lng=lng,
                                   gps_lat=gps_lat, gps_lng=gps_lng, building=building, floor=floor, note=note)


@router.post("/{job_id}/clarify", response_model=JobOut, response_model_exclude_unset=True)
def api_clarify(job_id: str, body: ClarifyRequest, background: BackgroundTasks, user=Depends(current_user)):
    return reporting.clarify(job_id, body.choice, user, background)
