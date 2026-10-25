from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile

from core.security import require_staff
from schemas.admin import FixResult, GroupedOut, HeatmapOut, MarkFakeResult
from schemas.reports import JobOut
from services import issues, reporting, verification
from services.storage import read_image

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/issues/grouped", response_model=GroupedOut, response_model_exclude_unset=True)
def api_grouped(user=Depends(require_staff)):
    return issues.grouped()


@router.get("/heatmap", response_model=HeatmapOut, response_model_exclude_unset=True)
def api_heatmap(user=Depends(require_staff)):
    return issues.heatmap()


@router.post("/issues/{issue_id}/fix", response_model=FixResult, response_model_exclude_unset=True)
async def api_fix(issue_id: str, image: UploadFile = File(...), capture_token: str = Form(...),
                  note: Optional[str] = Form(None), user=Depends(require_staff)):
    """Repair photo; Gemma audits it before students are asked to verify."""
    data = await read_image(image)
    return await verification.submit_fix(issue_id, data, capture_token, note, user)


@router.post("/reports/{report_id}/accept", response_model=JobOut, response_model_exclude_unset=True)
def api_accept_flagged(report_id: str, background: BackgroundTasks, user=Depends(require_staff)):
    """A flagged photo is genuine: group and rank it like a normal report."""
    return reporting.accept_flagged(report_id, user, background)


@router.post("/reports/{report_id}/mark-fake", response_model=MarkFakeResult, response_model_exclude_unset=True)
async def api_mark_fake(report_id: str, image: UploadFile = File(...), capture_token: str = Form(...),
                        user=Depends(require_staff)):
    """Needs a proof photo of the reported spot showing no problem; Gemma decides."""
    data = await read_image(image)
    return await verification.mark_fake(report_id, data, capture_token, user)
