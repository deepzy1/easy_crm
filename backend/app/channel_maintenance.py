"""Explicit PII minimization: run daily, python -m app.channel_maintenance.

Keep receipt hashes/IDs to prevent replay after the minimized event is redacted.
CRM/contact and qualification records follow the existing subject deletion flow.
"""

from datetime import timedelta

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.entities import InboundEvent, WebhookLog, now


def purge(db):
    cutoff = now() - timedelta(days=30)
    db.execute(delete(WebhookLog).where(WebhookLog.created_at < cutoff))
    for event in db.scalars(
        select(InboundEvent).where(
            InboundEvent.received_at < cutoff, InboundEvent.status.in_(["done", "cancelled", "failed"])
        )
    ):
        event.envelope = {"redacted": True}
    db.commit()


if __name__ == "__main__":
    with SessionLocal() as db:
        purge(db)
