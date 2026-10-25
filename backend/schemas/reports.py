from typing import List, Optional

from pydantic import BaseModel

from schemas.common import Out


class ClarifyRequest(BaseModel):
    choice: str  # "photo" = go with what the photo shows


class JobOut(Out):
    """A background job; follow it on GET /api/stream/{job_id} (SSE) or poll /api/stream/{job_id}/events."""
    job_id: str


class JobEvent(Out):
    id: int
    step: Optional[int] = None
    kind: str          # thought | tool_call | final | error
    text: str


class JobEventsOut(Out):
    events: List[JobEvent]


class DashboardVersion(Out):
    """Latest ledger block; the dashboard refreshes when block_no changes."""
    block_no: int
    event: Optional[str] = None
    issue_id: Optional[str] = None
