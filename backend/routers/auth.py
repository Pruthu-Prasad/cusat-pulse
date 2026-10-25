from fastapi import APIRouter, Depends, Request

from core import sessions
from core.database import get_db
from core.errors import AppError
from core.security import current_user, request_otp, token_from_request, verify_otp
from schemas.auth import AuthOut, CaptureTokenOut, MeOut, OkOut, OtpRequest, OtpSent, OtpVerify, SessionsOut
from services import antifake, issues

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/auth/request-otp", response_model=OtpSent, response_model_exclude_unset=True)
def api_request_otp(body: OtpRequest):
    return request_otp(body.name, body.email, body.cusat_id)


@router.post("/auth/verify-otp", response_model=AuthOut, response_model_exclude_unset=True)
def api_verify_otp(body: OtpVerify, request: Request):
    return verify_otp(body.email, body.code, request.headers.get("user-agent"))


@router.post("/auth/logout", response_model=OkOut, response_model_exclude_unset=True)
def api_logout(request: Request, user=Depends(current_user)):
    """Ends this device's session on the server; the token stops working immediately."""
    with get_db() as conn:
        sessions.revoke(conn, token_from_request(request))
    return {"ok": True}


@router.post("/auth/logout-all", response_model=OkOut, response_model_exclude_unset=True)
def api_logout_all(user=Depends(current_user)):
    """Ends every session of this account, on every device, including this one."""
    with get_db() as conn:
        return {"ok": True, "revoked": sessions.revoke_all(conn, user["id"])}


@router.get("/auth/sessions", response_model=SessionsOut, response_model_exclude_unset=True)
def api_sessions(request: Request, user=Depends(current_user)):
    """The devices currently signed in to this account."""
    with get_db() as conn:
        return {"sessions": sessions.list_for(conn, user["id"], token_from_request(request))}


@router.post("/auth/sessions/{session_id}/revoke", response_model=OkOut, response_model_exclude_unset=True)
def api_revoke_session(session_id: str, user=Depends(current_user)):
    """Signs out one of this account's other devices."""
    with get_db() as conn:
        if not sessions.revoke_by_public_id(conn, user["id"], session_id):
            raise AppError(404, "That device is not signed in.")
    return {"ok": True}


@router.get("/me", response_model=MeOut, response_model_exclude_unset=True)
def api_me(user=Depends(current_user)):
    return issues.my_reports(user)


@router.post("/capture-token", response_model=CaptureTokenOut, response_model_exclude_unset=True)
def api_capture_token(user=Depends(current_user)):
    """One-time token minted while the in-app camera is open; uploads without a fresh one are refused."""
    with get_db() as conn:
        return {"token": antifake.issue_capture_token(conn, user["id"]), "expires_in": 120}
