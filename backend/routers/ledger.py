from typing import Optional

from fastapi import APIRouter, Depends

from core.security import require_admin
from schemas.ledger import LedgerPage, VerifyResult
from services import ledger

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


@router.get("", response_model=LedgerPage, response_model_exclude_unset=True)
def api_ledger(issue_id: Optional[str] = None, page: int = 1, user=Depends(require_admin)):
    return ledger.page(issue_id, page)


@router.get("/verify", response_model=VerifyResult, response_model_exclude_unset=True)
def api_ledger_verify(user=Depends(require_admin)):
    """Recomputes every hash and cross-checks issue statuses against the chain."""
    return ledger.verify_now()
