"""Readiness exposes dependency status only, never configuration or exception text."""

from sqlalchemy import select, text

from app.core.database import SessionLocal
from app.core.config import get_settings
from app.models.entities import WorkerHeartbeat, now

SCHEMA_REVISION = "c82d4f7e1a50"


def readiness():
    try:
        with SessionLocal() as db:
            version = db.scalar(text("SELECT version_num FROM alembic_version"))
            if version != SCHEMA_REVISION:
                return {"status": "unavailable", "database": "connected", "schema": "migration_required"}
            heartbeat = db.scalar(select(WorkerHeartbeat.last_seen).where(WorkerHeartbeat.name == "channels"))
            fresh = heartbeat is not None and (now() - heartbeat).total_seconds() < 180
            ready = fresh or not get_settings().require_worker_ready
            return {
                "status": "ok" if ready else "unavailable",
                "database": "connected",
                "schema": "current",
                "worker": "recent" if fresh else "stale_or_not_started",
            }
    except Exception:
        return {"status": "unavailable", "database": "unavailable"}
