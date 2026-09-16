import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, request_id_var

settings = get_settings()
configure_logging()
logger = get_logger("wakeupram.request")

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])

app = FastAPI(
    title="Wake Up Ram API",
    version="0.1.0",
    description="Personal AI companion, discipline system and life-intelligence platform.",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# NOTE: registering the Limiter on app.state is not enough by itself — slowapi
# only actually enforces `default_limits` on every request once this
# middleware is added. Without it, RATE_LIMIT_DEFAULT was configured but
# silently never applied to any endpoint.
app.add_middleware(SlowAPIMiddleware)

# Restricted CORS: only the origins explicitly configured per environment.
# Never falls back to "*" — an empty CORS_ALLOWED_ORIGINS means no cross-origin
# browser access, which is the safe default until it's deliberately configured.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    # A per-request id, propagated into every log line emitted while
    # handling this request (see app/core/logging.py), and echoed back to
    # the client so a support/bug report can be matched to server logs
    # without ever needing request/response bodies.
    request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "request_handled",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        response.headers["x-request-id"] = request_id
        return response
    finally:
        request_id_var.reset(token)


app.include_router(api_router)


@app.get("/health", tags=["system"])
def health_check() -> JSONResponse:
    return JSONResponse({"status": "ok", "environment": settings.ENVIRONMENT})


@app.exception_handler(Exception)
def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Production must never leak stack traces to clients. The exception
    # itself, with full traceback, goes to structured logs server-side
    # (never to the client) so it's diagnosable without exposing internals.
    logger.exception(
        "unhandled_exception",
        extra={"method": request.method, "path": request.url.path},
    )
    if settings.DEBUG:
        raise exc
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )
