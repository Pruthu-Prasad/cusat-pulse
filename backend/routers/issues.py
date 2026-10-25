from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile

from core.security import current_user
from schemas.issues import CheckResult, IssueDetail, IssueListOut
from services import issues, verification
from services.storage import read_image

router = APIRouter(prefix="/api/issues", tags=["issues"])


@router.get("", response_model=IssueListOut, response_model_exclude_unset=True)
def api_issues(include_resolved: bool = False, user=Depends(current_user)):
    return issues.list_for_map(user, include_resolved)


@router.get("/{issue_id}", response_model=IssueDetail, response_model_exclude_unset=True)
def api_issue(issue_id: str, user=Depends(current_user)):
    return issues.detail(issue_id, user)


@router.post("/{issue_id}/confirm", response_model=CheckResult, response_model_exclude_unset=True)
async def api_confirm(issue_id: str, background: BackgroundTasks, image: UploadFile = File(...),
                      capture_token: str = Form(...), user=Depends(current_user)):
    """Student says the repair worked; needs a current photo that Gemma verifies."""
    data = await read_image(image)
    return await verification.student_check(issue_id, data, capture_token, user, "resolved", background)


@router.post("/{issue_id}/dispute", response_model=CheckResult, response_model_exclude_unset=True)
async def api_dispute(issue_id: str, background: BackgroundTasks, image: UploadFile = File(...),
                      capture_token: str = Form(...), user=Depends(current_user)):
    """Student says the repair didn't work; needs a current photo that Gemma verifies."""
    data = await read_image(image)
    return await verification.student_check(issue_id, data, capture_token, user, "unresolved", background)
