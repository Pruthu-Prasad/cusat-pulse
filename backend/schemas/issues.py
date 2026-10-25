from typing import Any, Dict, List, Optional

from schemas.common import Out


class IssueLink(Out):
    issue_a: str
    issue_b: str
    note: Optional[str] = None


class IssueSummary(Out):
    """One map pin."""
    id: str
    title: Optional[str] = None
    category: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    status: str
    threat_level: Optional[str] = None
    severity: Optional[int] = None
    unique_reporters: Optional[int] = None
    priority: Optional[float] = None
    fix_disputed: Optional[int] = None
    failed_fix_attempts: Optional[int] = None
    created_at: Optional[str] = None


class IssueListOut(Out):
    issues: List[IssueSummary]
    links: List[IssueLink]


class Breakdown(Out):
    inputs: Dict[str, Any]
    parts: Dict[str, float]
    priority: float


class IssueReport(Out):
    """A report inside an issue. name / cusat_id / trust_score / note / gps_flag are staff-only."""
    id: str
    image_path: Optional[str] = None
    ai_description: Optional[str] = None
    advice: Optional[str] = None
    severity: Optional[int] = None
    emergency: Optional[int] = None
    complexity: Optional[int] = None
    confidence: Optional[float] = None
    hazard_box: Optional[str] = None
    merge_type: Optional[str] = None
    merge_reason: Optional[str] = None
    counts_toward_total: Optional[int] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    floor: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    name: Optional[str] = None
    cusat_id: Optional[str] = None
    trust_score: Optional[int] = None
    note: Optional[str] = None
    gps_flag: Optional[str] = None


class Audit(Out):
    kind: str
    image_path: Optional[str] = None
    same_location_verified: Optional[int] = None
    passed: Optional[int] = None
    reason: Optional[str] = None
    created_at: Optional[str] = None


class IssueLedgerBlock(Out):
    block_no: int
    event: str
    report_id: Optional[str] = None
    actor: Optional[str] = None
    block_hash: str
    created_at: str


class IssueDetail(Out):
    """Full issue. work_order_en / work_order_ml / ledger are staff-only; other issue columns pass through."""
    id: str
    title: Optional[str] = None
    category: Optional[str] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    status: str
    severity: Optional[int] = None
    threat_level: Optional[str] = None
    priority: Optional[float] = None
    unique_reporters: Optional[int] = None
    summary: Optional[str] = None
    rank_reason: Optional[str] = None
    verify_deadline: Optional[str] = None
    breakdown: Breakdown
    rank: int
    reports: List[IssueReport]
    audits: List[Audit]
    after_photo: Optional[str] = None
    i_reported: bool
    links: List[IssueLink]
    work_order_en: Optional[str] = None
    work_order_ml: Optional[str] = None
    ledger: Optional[List[IssueLedgerBlock]] = None


class CheckResult(Out):
    """Student verification of a repair (confirm or dispute), decided by Gemma's photo verdict."""
    outcome: str          # resolved | unresolved | rejected
    claim: str            # resolved | unresolved
    accepted: bool
    message: str
    reason: Optional[str] = None
    verified: bool        # kept for older clients: True when the issue was reopened
