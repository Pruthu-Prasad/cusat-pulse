"""One error type for the service layer, so services don't depend on FastAPI. Responses keep FastAPI's shape."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """A user-facing failure: HTTP status + a plain message shown in the UI."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def install_handlers(app: FastAPI):
    @app.exception_handler(AppError)
    async def app_error(_request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def plain_errors(_request: Request, exc: Exception):
        print(f"[error] {exc!r}", flush=True)
        return JSONResponse(status_code=500, content={"detail": "Something went wrong on our side. Please try again."})
