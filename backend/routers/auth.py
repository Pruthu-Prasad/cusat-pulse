from fastapi import APIRouter, Depends

from core.database import get_db
from core.security import current_user, request_otp, verify_otp
from schemas.auth import AuthOut, CaptureTokenOut, MeOut, OtpRequest, OtpSent, OtpVerify
from services import antifake, issues

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/request-otp", response_model=OtpSent, response_model_exclude_unset=True)
def api_request_otp(body: OtpRequest):
    return request_otp(body.name, body.email, body.cusat_id)


@router.post("/auth/verify-otp", response_model=AuthOut, response_model_exclude_unset=True)
def api_verify_otp(body: OtpVerify):
    return verify_otp(body.email, body.code)


@router.get("/me", response_model=MeOut, response_model_exclude_unset=True)
def api_me(user=Depends(current_user)):
    return issues.my_reports(user)


@router.post("/capture-token", response_model=CaptureTokenOut, response_model_exclude_unset=True)
def api_capture_token(user=Depends(current_user)):
    """One-time token minted while the in-app camera is open; uploads without a fresh one are refused."""
    with get_db() as conn:
        return {"token": antifake.issue_capture_token(conn, user["id"]), "expires_in": 120}
