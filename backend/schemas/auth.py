from typing import List, Optional

from pydantic import BaseModel

from schemas.common import Out


# ---------- requests ----------

class OtpRequest(BaseModel):
    email: str
    name: Optional[str] = None
    cusat_id: Optional[str] = None


class OtpVerify(BaseModel):
    email: str
    code: str


# ---------- responses ----------

class OtpSent(Out):
    sent: bool
    new_user: bool
    demo_hint: Optional[str] = None


class UserOut(Out):
    id: int
    name: str
    email: str
    cusat_id: str
    role: str
    trust_score: int


class AuthOut(Out):
    token: str
    user: UserOut


class CaptureTokenOut(Out):
    token: str
    expires_in: int


class MyReport(Out):
    id: str
    issue_id: Optional[str] = None
    image_path: Optional[str] = None
    ai_description: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[int] = None
    report_status: Optional[str] = None
    created_at: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    threat_level: Optional[str] = None
    verify_deadline: Optional[str] = None
    unique_reporters: Optional[int] = None
    fix_disputed: Optional[int] = None
    after_photo: Optional[str] = None
    already_confirmed: Optional[bool] = None


class MeOut(Out):
    user: UserOut
    reports: List[MyReport]
