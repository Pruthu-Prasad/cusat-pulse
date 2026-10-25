"""CUSAT-Pulse API. Run: uvicorn main:app --port 8000

Layout: core/ (config, database, security, errors) · schemas/ (request + response models)
routers/ (HTTP endpoints) · services/ (business logic) · ai/ (Gemma client, prompts, schemas, tasks)
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.database import init_db
from core.errors import install_handlers
from routers import admin, auth, issues, ledger, reports, stream, system
from services.scheduler import scheduler_loop


@asynccontextmanager
async def lifespan(_app):
    init_db()
    task = asyncio.create_task(scheduler_loop())  # verification deadlines, auto-dismiss, re-rank
    yield
    task.cancel()


app = FastAPI(title="CUSAT-Pulse", lifespan=lifespan)
install_handlers(app)

for r in (auth, reports, stream, issues, admin, ledger, system):
    app.include_router(r.router)
