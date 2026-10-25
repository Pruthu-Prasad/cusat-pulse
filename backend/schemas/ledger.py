from typing import List, Optional

from schemas.common import Out


class LedgerBlock(Out):
    block_no: int
    event: str
    issue_id: Optional[str] = None
    report_id: Optional[str] = None
    actor: Optional[str] = None
    prev_hash: str
    block_hash: str
    created_at: str


class LedgerPage(Out):
    blocks: List[LedgerBlock]
    total: int
    latest_hash: Optional[str] = None


class VerifyResult(Out):
    intact: bool
    blocks: int
    latest_hash: Optional[str] = None   # when intact
    broken_at: Optional[int] = None     # when broken
    issue_id: Optional[str] = None
    reason: Optional[str] = None


class SeedResult(Out):
    seeded: bool
    message: Optional[str] = None
