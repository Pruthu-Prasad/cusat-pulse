from pydantic import BaseModel

from schemas.common import Out


class ClarifyRequest(BaseModel):
    choice: str  # "photo" = go with what the photo shows


class JobOut(Out):
    """A background job; follow it on GET /api/stream/{job_id}."""
    job_id: str
