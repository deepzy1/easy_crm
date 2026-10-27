import json
import logging
import time
import re
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware

from app.ai.providers import ProviderError
from app.api import ai, auth, channels, crm, knowledge, operations, qualification
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.services.operations import readiness

logger = logging.getLogger("easycrm")
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
settings = get_settings()


@asynccontextmanager
async def lifespan(app):
    if settings.environment == "production":
        if len(settings.webhook_master_key.get_secret_value()) < 32:
            raise RuntimeError("Production requires a stable WEBHOOK_MASTER_KEY of at least 32 characters")
        if not settings.cookie_secure or any(not x.startswith("https://") for x in settings.cors_origins):
            raise RuntimeError("Production requires secure cookies and HTTPS CORS origins")
        # Worker readiness is checked by the endpoint after the worker starts.
        status = readiness()
        if status.get("schema") != "current":
            raise RuntimeError("Database unavailable or migrations required; run alembic upgrade head")
    yield
    engine.dispose()


app = FastAPI(
    title="EasyCRM",
    version="0.5.0",
    description="CRM, reviewed knowledge, qualification, channels and operational analytics",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Request-ID"],
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
    response = None
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        # Cookie authentication requires a trusted browser Origin. CLI Bearer clients need no Origin.
        if (origin and origin not in settings.cors_origins) or (
            request.cookies.get("easycrm_session") and not origin and not request.headers.get("authorization")
        ):
            response = error(request, 403, "origin_rejected", "Request origin is not allowed")
        if response is None:
            limit = (
                2 * 1024 * 1024
                if re.fullmatch(r"/api/v1/workspaces/[0-9a-f-]{36}/knowledge/uploads", request.url.path)
                else 65536
            )
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > limit:
                    response = error(request, 413, "body_too_large", "Request body is too large")
                    break
            request._body = bytes(body)
    try:
        if response is None:
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


@app.get("/api/v1/health/live", tags=["Health"])
def live():
    return {"status": "ok"}


@app.get("/api/v1/health/ready", tags=["Health"])
def ready():
    status = readiness()
    return JSONResponse(status_code=200 if status["status"] == "ok" else 503, content=status)


for router in (
    auth.router,
    crm.router,
    ai.router,
    qualification.router,
    channels.router,
    knowledge.router,
    operations.router,
):
    app.include_router(router, prefix="/api/v1")
