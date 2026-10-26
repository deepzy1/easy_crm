import json
import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from app.ai.providers import ProviderError
from app.api import ai, auth, crm
from app.core.config import get_settings
from app.core.database import SessionLocal

logger = logging.getLogger("easycrm")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
app = FastAPI(title="EasyCRM", version="0.1.0", description="Session 1 CRM foundation and AI playground")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def error(request, status, code, message, details=None):
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", ""),
                "details": details or {},
            }
        },
    )


@app.middleware("http")
async def security_and_logging(request: Request, call_next):
    request.state.request_id = str(uuid4())
    start = time.monotonic()
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        # Cookie authentication requires a trusted browser Origin. CLI Bearer clients need no Origin.
        if (origin and origin not in settings.cors_origins) or (
            request.cookies.get("easycrm_session") and not origin and not request.headers.get("authorization")
        ):
            return error(request, 403, "origin_rejected", "Request origin is not allowed")
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                return error(request, 413, "body_too_large", "Request body is too large")
        request._body = bytes(body)
    try:
        response = await call_next(request)
    except Exception:
        # Never log exception messages, request bodies, headers, query strings, or provider responses.
        logger.error(json.dumps({"event": "request_failed", "request_id": request.state.request_id}))
        response = error(request, 500, "internal_error", "An unexpected error occurred")
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    route = request.scope.get("route")
    logger.info(
        json.dumps(
            {
                "event": "request",
                "request_id": request.state.request_id,
                "method": request.method,
                "route": getattr(route, "path", "unmatched"),
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - start) * 1000),
            }
        )
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error(request, exc.status_code, f"http_{exc.status_code}", str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic errors can contain input passwords; expose only field locations and generic categories.
    return error(
        request,
        422,
        "validation_error",
        "Check the submitted fields",
        {"fields": [{"field": ".".join(str(p) for p in e["loc"]), "type": e["type"]} for e in exc.errors()]},
    )


@app.exception_handler(ProviderError)
async def provider_error(request, exc):
    return error(request, exc.status, exc.code, exc.message, {"upstream_status": exc.upstream_status})


@app.get("/api/v1/health", tags=["Health"])
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "disconnected"})


for router in (auth.router, crm.router, ai.router):
    app.include_router(router, prefix="/api/v1")
