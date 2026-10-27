from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.crm import scoped_lead
from app.core.database import get_db
from app.core.security import admin, member
from app.models.entities import (
    ChannelContact,
    ChannelMessage,
    ChannelThread,
    InboundEvent,
    Integration,
    Lead,
    Note,
    PrivacyAudit,
    QualificationConversation,
    QualificationEvent,
    Stage,
    WorkerHeartbeat,
)

router = APIRouter(prefix="/workspaces/{ws}", tags=["Analytics & privacy"])


@router.get("/analytics/operations")
def analytics(
    ws: UUID,
    since: datetime | None = None,
    until: datetime | None = None,
    membership=Depends(member),
    db: Session = Depends(get_db),
):
    for value in (since, until):
        if value and value.tzinfo is None:
            raise HTTPException(422, "Use timestamps with a timezone")
    if since and until and since >= until:
        raise HTTPException(422, "Start must be before end")

    def scope(model, timestamp):
        clauses = [model.workspace_id == str(ws)]
        if since:
            clauses.append(timestamp >= since)
        if until:
            clauses.append(timestamp < until)
        return clauses

    def groups(model, field, timestamp):
        return dict(
            db.execute(select(field, func.count()).where(*scope(model, timestamp)).group_by(field)).all()
        )

    sources = groups(Lead, Lead.source, Lead.created_at)
    statuses = groups(Lead, Lead.status, Lead.created_at)
    total = sum(sources.values())
    # Every count uses actual records, never model output guesses or synthetic KPI constants.
    lead_scope = scope(Lead, Lead.created_at)
    pipeline = db.execute(
        select(Stage.name, func.count(Lead.id))
        .outerjoin(Lead, and_(Lead.stage_id == Stage.id, *lead_scope))
        .where(Stage.workspace_id == str(ws))
        .group_by(Stage.id)
        .order_by(Stage.position)
    ).all()
    receipts = groups(InboundEvent, InboundEvent.status, InboundEvent.received_at)
    messages = groups(ChannelMessage, ChannelMessage.status, ChannelMessage.created_at)
    events = db.scalars(
        select(QualificationEvent).where(*scope(QualificationEvent, QualificationEvent.created_at))
    ).all()
    handoff_conversations = set()
    latencies = []
    for event in events:
        payload = event.payload
        after = payload.get("plan") or payload.get("after") or {}
        before = payload.get("before") or {}
        if (
            after.get("mode") == "human"
            and after.get("state") in {"qualified", "needs_human"}
            and before.get("mode") != "human"
        ):
            handoff_conversations.add(event.conversation_id)
        model = (payload.get("plan") or {}).get("model") or {}
        if isinstance(model.get("latency_ms"), (int, float)):
            latencies.append(model["latency_ms"])
    processing = db.scalars(
        select(func.extract("epoch", InboundEvent.processed_at - InboundEvent.received_at) * 1000).where(
            *scope(InboundEvent, InboundEvent.received_at), InboundEvent.processed_at.is_not(None)
        )
    ).all()
    heartbeat = (
        db.scalar(select(WorkerHeartbeat.last_seen).where(WorkerHeartbeat.name == "channels"))
        if membership.role == "admin"
        else None
    )
    return {
        "window": {"since": since, "until": until, "timezone": "UTC", "end_exclusive": True},
        "total_leads": total,
        "inbound_leads": sum(
            v for k, v in sources.items() if k in {"website", "whatsapp", "meta", "instagram"}
        ),
        "sources": sources,
        "statuses": statuses,
        "qualification_rate": round(statuses.get("qualified", 0) / total * 100, 1) if total else 0,
        "handoff_conversations": len(handoff_conversations),
        "pipeline": [{"name": name, "count": count} for name, count in pipeline],
        "receipts": receipts,
        "messages": messages,
        "processing_failures": receipts.get("failed", 0),
        "message_failures": messages.get("failed", 0),
        "ambiguous_sends": messages.get("unknown", 0),
        "inference_latency_ms": {
            "samples": len(latencies),
            "mean": round(sum(latencies) / len(latencies), 1) if latencies else None,
        },
        "intake_processing_ms": {
            "samples": len(processing),
            "mean": round(float(sum(processing)) / len(processing), 1) if processing else None,
        },
        "worker_last_seen": heartbeat,
        "definitions": {
            "leads": "Current status and stage of leads created in [start, end). All sources, including manual and fictional demo records. Inbound means website, WhatsApp, Meta or Instagram source; labels alone do not prove webhook origin.",
            "rate": "Currently qualified leads divided by all leads in the creation cohort; closed and disqualified remain in the denominator. No revenue conversion claim.",
            "handoffs": "Distinct conversations with a recorded qualification handoff or human takeover during the window. Repeated events count once; closed/opt-out excluded.",
            "failures": "Current receipt/message states for records received/created in the window. Retries that later succeed leave the failed count; unknown sends are separate.",
            "timing": "Mean successful recorded provider latency, including simulator/mock fixtures when used. Intake timing: receipt to terminal processing, including queue/retry delay, only since Session 5. Excludes delivery/network time; no samples shows unavailable.",
        },
    }


def subject_rows(db, ws, lead_id):
    contacts = db.scalars(
        select(ChannelContact).where(
            ChannelContact.workspace_id == str(ws), ChannelContact.lead_id == str(lead_id)
        )
    ).all()
    threads = (
        db.scalars(
            select(ChannelThread).where(
                ChannelThread.workspace_id == str(ws), ChannelThread.contact_id.in_([c.id for c in contacts])
            )
        ).all()
        if contacts
        else []
    )
    conversations = db.scalars(
        select(QualificationConversation).where(
            QualificationConversation.workspace_id == str(ws),
            QualificationConversation.lead_id == str(lead_id),
        )
    ).all()
    return contacts, threads, conversations


def serialize(row):
    return {column.name: getattr(row, column.name) for column in row.__table__.columns}


@router.get("/leads/{lead_id}/export")
def export(ws: UUID, lead_id: UUID, membership=Depends(admin), db: Session = Depends(get_db)):
    lead = scoped_lead(db, ws, lead_id)
    contacts, threads, conversations = subject_rows(db, ws, lead_id)
    # IDs and ordinary CRM data only; no integration signing keys or provider credentials.
    tables = {
        "notes": db.scalars(
            select(Note).where(Note.workspace_id == str(ws), Note.lead_id == str(lead_id))
        ).all(),
        "contacts": contacts,
        "threads": threads,
        "conversations": conversations,
        "messages": db.scalars(
            select(ChannelMessage).where(
                ChannelMessage.workspace_id == str(ws), ChannelMessage.thread_id.in_([r.id for r in threads])
            )
        ).all(),
        "qualification_events": db.scalars(
            select(QualificationEvent).where(
                QualificationEvent.workspace_id == str(ws),
                QualificationEvent.conversation_id.in_([r.id for r in conversations]),
            )
        ).all(),
    }
    db.add(
        PrivacyAudit(
            workspace_id=str(ws), actor_id=membership.user_id, action="export", subject_id=str(lead_id)
        )
    )
    db.commit()
    return {
        "lead": serialize(lead),
        **{key: [serialize(row) for row in rows] for key, rows in tables.items()},
    }


def erase_subject(db, ws, lead, actor):
    """Redact linked minimized receipts; row cascades erase subject history.

    Unprocessed receipts cannot always be linked safely, so deletion is blocked
    while intake is active. Completed envelopes match exact normalized identities.
    """
    integrations = db.scalars(
        select(Integration)
        .where(Integration.workspace_id == str(ws))
        .order_by(Integration.id)
        .with_for_update()
    ).all()
    if any(row.active for row in integrations):
        raise HTTPException(
            409,
            "Deactivate workspace integrations before subject deletion, then drain or recover pending intake",
        )
    pending = db.scalar(
        select(InboundEvent.id)
        .where(
            InboundEvent.workspace_id == str(ws),
            InboundEvent.status.in_(["pending", "qualify", "processing"]),
        )
        .limit(1)
    )
    if pending:
        raise HTTPException(
            409, "Pause integrations and drain/recover pending workspace intake before deleting a subject"
        )
    contacts, threads, _ = subject_rows(db, ws, lead.id)
    identities = {
        lead.id,
        lead.email.casefold(),
        lead.phone,
        *[c.identity.split(":", 1)[-1] for c in contacts],
        *[t.external_contact_id for t in threads],
    } - {""}
    for receipt in db.scalars(select(InboundEvent).where(InboundEvent.workspace_id == str(ws))):
        envelope = receipt.envelope
        values = set()

        def collect(value):
            if isinstance(value, dict):
                for k, v in value.items():
                    if k in {
                        "email",
                        "phone",
                        "external_contact_id",
                        "external_id",
                        "contact_id",
                        "lead_id",
                    } and isinstance(v, str):
                        values.add(v.casefold())
                    elif isinstance(v, (dict, list)):
                        collect(v)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(envelope)
        if values & {v.casefold() for v in identities}:
            receipt.envelope = {"redacted": True}
    db.add(PrivacyAudit(workspace_id=str(ws), actor_id=actor, action="erase", subject_id=lead.id))
    db.delete(lead)


@router.get("/privacy/audit")
def audits(
    ws: UUID, limit: int = Query(50, ge=1, le=100), membership=Depends(admin), db: Session = Depends(get_db)
):
    return db.scalars(
        select(PrivacyAudit)
        .where(PrivacyAudit.workspace_id == str(ws))
        .order_by(PrivacyAudit.created_at.desc())
        .limit(limit)
    ).all()
