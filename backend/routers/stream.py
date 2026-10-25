"""Server-Sent Events. Both streams poll the database (agent_events / ledger), so they survive restarts."""
import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core.database import get_db, rows
from core.security import current_user, require_staff

router = APIRouter(prefix="/api/stream", tags=["stream"])


def sse(gen):
    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# Registered before /{job_id} so "dashboard" is never read as a job id.
@router.get("/dashboard")
async def api_stream_dashboard(user=Depends(require_staff)):
    async def gen():
        last, idle = None, 0
        yield ": connected\n\n"  # flush headers now so the browser marks the stream open
        # End after ~5 minutes; EventSource reconnects by itself, and a finite stream lets the server reload/shut down.
        while idle < 600:
            with get_db() as conn:
                row = conn.execute("SELECT block_no, event, issue_id FROM ledger ORDER BY block_no DESC LIMIT 1").fetchone()
            cur = dict(row) if row else {"block_no": 0}
            if cur["block_no"] != (last or {}).get("block_no"):
                if last is not None:
                    yield f"data: {json.dumps(cur)}\n\n"
                last, idle = cur, 0
            idle += 1
            if idle % 20 == 0:
                yield ": ping\n\n"
            await asyncio.sleep(0.5)
    return sse(gen())


@router.get("/{job_id}")
async def api_stream_job(job_id: str, user=Depends(current_user)):
    async def gen():
        last_id, ticks = 0, 0
        yield ": connected\n\n"
        while ticks < 600:  # 5 minutes max
            with get_db() as conn:
                evs = rows(conn.execute("SELECT id, step, kind, text FROM agent_events WHERE report_id=? AND id>? ORDER BY id",
                                        (job_id, last_id)))
            for e in evs:
                last_id = e["id"]
                yield f"data: {json.dumps(e)}\n\n"
                if e["kind"] in ("final", "error"):
                    return
            ticks += 1
            if ticks % 20 == 0:
                yield ": ping\n\n"
            await asyncio.sleep(0.5)
    return sse(gen())
