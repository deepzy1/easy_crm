"""Workspace management, signed public callbacks, and the unified inbox."""

import hashlib
import hmac
import json
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.telemetry import record
from app.core.security import admin, limiter, member
from app.integrations import meta
from app.models.entities import (
    ChannelContact as Contact,
    ChannelMessage as Message,
    ChannelThread as Thread,
    InboundEvent as Event,
    Integration,
    Lead,
    QualificationConversation,
    WebhookLog,
    now,
    uid,
)
from app.schemas.channels import IntegrationInput, IntegrationPatch, ManualMessage, ThreadControl
from app.services import channels, webhooks

router = APIRouter(tags=["Channels & Inbox"])


def integration_out(row):
    configured = (
        len(get_settings().webhook_master_key.get_secret_value()) >= 32 if row.kind == "website" else True
    )
    if row.kind != "website":
        try:
            meta.connection(row)
        except HTTPException:
            configured = False
    return {
        "id": row.id,
        "name": row.name,
        "kind": row.kind,
        "active": row.active,
        "ai_enabled": row.ai_enabled,
        "field_map": row.field_map,
        "configured": configured,
        "webhook_url": f"/api/v1/webhooks/{'forms' if row.kind == 'website' else 'meta'}/{row.id}",
        "verification": "not_live_verified",
    }


@router.get("/workspaces/{ws}/integrations")
def integrations(ws: UUID, membership=Depends(admin), db: Session = Depends(get_db)):
    return {
        "items": [
            integration_out(r)
            for r in db.scalars(
                select(Integration)
                .where(Integration.workspace_id == str(ws))
                .order_by(Integration.created_at)
            )
        ],
        "website_configured": len(get_settings().webhook_master_key.get_secret_value()) >= 32,
        "meta_credentials": [
            {"alias": key, "kind": value.kind}
            for key, value in get_settings().meta_connections.items()
            if value.workspace_id == str(ws)
        ],
        "limits": "WhatsApp text replies only, within 24 hours. Instagram is receive-only. Facebook requires leads_retrieval. No live verification claimed.",
    }


@router.post("/workspaces/{ws}/integrations", status_code=201)
def integration_create(
    ws: UUID, body: IntegrationInput, membership=Depends(admin), db: Session = Depends(get_db)
):
    row = Integration(workspace_id=str(ws), **body.model_dump())
    row.id, row.key_version = uid(), 1
    secret = None
    if body.kind == "website":
        if body.credential_alias:
            raise HTTPException(422, "Website integrations do not use Meta credentials")
        secret = webhooks.signing_secret(row)
    else:
        config = get_settings().meta_connections.get(body.credential_alias)
        if not config or config.workspace_id != str(ws) or config.kind != body.kind:
            raise HTTPException(
                422, "Configure an authorized credential alias for this workspace on the backend"
            )
        row.external_account_id = config.external_account_id
        meta.connection(row)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This Meta account is already connected") from None
    return {**integration_out(row), "signing_secret": secret}


@router.patch("/workspaces/{ws}/integrations/{integration_id}")
def integration_update(
    ws: UUID,
    integration_id: UUID,
    body: IntegrationPatch,
    membership=Depends(admin),
    db: Session = Depends(get_db),
):
    row = webhooks.get_integration(db, integration_id, ws, lock=True)
    row.active, row.ai_enabled = body.active, body.ai_enabled
    if not row.active or not row.ai_enabled:
        for thread in db.scalars(
            select(Thread).where(Thread.workspace_id == str(ws), Thread.integration_id == row.id)
        ):
            thread.mode, thread.control_version = "human", thread.control_version + 1
            channels.cancel_ai(db, ws, thread.id)
    db.commit()
    return integration_out(row)


@router.post("/workspaces/{ws}/integrations/{integration_id}/rotate")
def rotate(ws: UUID, integration_id: UUID, membership=Depends(admin), db: Session = Depends(get_db)):
    row = webhooks.get_integration(db, integration_id, ws, lock=True)
    if row.kind != "website":
        raise HTTPException(409, "Rotate Meta tokens on the backend and restart API and worker")
    row.key_version += 1
    secret = webhooks.signing_secret(row)
    db.commit()
    return {"signing_secret": secret, "old_key_revoked": True}


@router.post("/workspaces/{ws}/integrations/{integration_id}/test")
async def test_integration(
    ws: UUID, integration_id: UUID, membership=Depends(admin), db: Session = Depends(get_db)
):
    row = webhooks.get_integration(db, integration_id, ws, active=True)
    limiter.check(f"channel_test:{ws}", 5, 60)
    if row.kind == "website":
        # Explicit fictional event goes through exactly the same verifier/normalizer/queue.
        import time

        event_id, stamp = "test-" + uid(), str(int(time.time()))
        values = {
            "name": "Webhook test prospect",
            "email": "webhook-test@example.com",
            "message": "Explicit integration test",
        }
        payload = {row.field_map.get(k, k): v for k, v in values.items()}
        raw = json.dumps({"lead": payload}).encode()
        signature = (
            "sha256="
            + hmac.new(
                webhooks.signing_secret(row).encode(),
                stamp.encode() + b"." + event_id.encode() + b"." + raw,
                hashlib.sha256,
            ).hexdigest()
        )
        result = webhooks.signed_website(
            db,
            row,
            raw,
            {"x-easycrm-event-id": event_id, "x-easycrm-timestamp": stamp, "x-easycrm-signature": signature},
        )
        webhooks.log(db, row, "test_accepted")
        db.commit()
        return {
            **result,
            "test_mode": True,
            "detail": "Fictional test queued; no external message will be sent",
        }
    try:
        result = await meta.graph(
            meta.connection(row), "GET", row.external_account_id, params={"fields": "id"}
        )
    except meta.MetaError as exc:
        raise HTTPException(502, exc.code) from None
    return {
        "connected": str(result.get("id")) == row.external_account_id,
        "detail": "Account lookup only; webhook permissions, delivery and inference still require live tests",
    }


@router.get("/workspaces/{ws}/integrations/deliveries")
def deliveries(ws: UUID, membership=Depends(admin), db: Session = Depends(get_db)):
    # No contact identifiers, message text, raw payloads or credential aliases in delivery logs.
    events = db.scalars(
        select(Event).where(Event.workspace_id == str(ws)).order_by(Event.received_at.desc()).limit(100)
    ).all()
    logs = db.scalars(
        select(WebhookLog)
        .where(WebhookLog.workspace_id == str(ws))
        .order_by(WebhookLog.created_at.desc())
        .limit(100)
    ).all()
    return {
        "events": [
            {
                "id": r.id,
                "integration_id": r.integration_id,
                "status": r.status,
                "attempts": r.attempts,
                "error": r.error,
                "received_at": r.received_at,
            }
            for r in events
        ],
        "requests": [
            {"id": r.id, "integration_id": r.integration_id, "result": r.result, "created_at": r.created_at}
            for r in logs
        ],
    }


@router.post("/workspaces/{ws}/integrations/deliveries/{delivery_id}/retry")
def retry(ws: UUID, delivery_id: UUID, membership=Depends(admin), db: Session = Depends(get_db)):
    event = db.scalar(
        select(Event).where(Event.workspace_id == str(ws), Event.id == str(delivery_id)).with_for_update()
    )
    if not event:
        raise HTTPException(404, "Delivery not found")
    if event.status != "failed" or event.envelope.get("redacted"):
        raise HTTPException(
            409, "Only failed deliveries can be retried; processing jobs require worker recovery"
        )
    event.status = "qualify" if event.envelope.get("thread_id") else "pending"
    event.processed_at = None
    event.available_at, event.error = now(), ""
    db.commit()
    return {"status": event.status, "detail": "Explicit retry may make a paid inference request"}


@router.post("/webhooks/forms/{integration_id}", status_code=202)
async def website_callback(integration_id: UUID, request: Request, db: Session = Depends(get_db)):
    row = webhooks.get_integration(db, integration_id, active=True, lock="key_share")
    if row.kind != "website":
        raise HTTPException(404, "Website integration not found")
    try:
        result = webhooks.signed_website(db, row, await request.body(), request.headers)
    except HTTPException as exc:
        db.rollback()
        webhooks.log(db, row, f"rejected_{exc.status_code}")
        db.commit()
        raise
    webhooks.log(db, row, result["status"])
    db.commit()
    record(
        "webhook_receipt",
        request_id=request.state.request_id,
        receipt_id=result["delivery_id"],
        workspace_id=row.workspace_id,
        status=result["status"],
    )
    return result


@router.get("/webhooks/meta/{integration_id}", response_class=PlainTextResponse)
def meta_challenge(integration_id: UUID, request: Request, db: Session = Depends(get_db)):
    row = webhooks.get_integration(db, integration_id, active=True)
    limiter.check(f"meta_challenge:{row.id}", 30, 60)
    if row.kind == "website":
        raise HTTPException(404, "Meta integration not found")
    config = meta.connection(row)
    query = request.query_params
    if query.get("hub.mode") != "subscribe" or not hmac.compare_digest(
        query.get("hub.verify_token", ""), config.verify_token.get_secret_value()
    ):
        raise HTTPException(403, "Webhook verification failed")
    challenge = query.get("hub.challenge", "")
    if not challenge or len(challenge) > 500:
        raise HTTPException(422, "Invalid challenge")
    return challenge


@router.post("/webhooks/meta/{integration_id}")
async def meta_callback(integration_id: UUID, request: Request, db: Session = Depends(get_db)):
    row = webhooks.get_integration(db, integration_id, active=True, lock="key_share")
    if row.kind == "website":
        raise HTTPException(404, "Meta integration not found")
    limiter.check(f"webhook:{row.id}", 300, 60)
    config = meta.connection(row)
    raw = await request.body()
    signature = (
        "sha256=" + hmac.new(config.app_secret.get_secret_value().encode(), raw, hashlib.sha256).hexdigest()
    )
    try:
        if not hmac.compare_digest(
            signature.encode(), request.headers.get("x-hub-signature-256", "").encode()
        ):
            raise HTTPException(401, "Invalid Meta signature")
        try:
            events = webhooks.meta_envelopes(row, json.loads(raw))
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            raise HTTPException(422, "Invalid Meta event") from None
        results = [webhooks.accept(db, row, identity, envelope) for identity, envelope in events]
    except HTTPException as exc:
        db.rollback()
        webhooks.log(db, row, f"rejected_{exc.status_code}")
        db.commit()
        raise
    webhooks.log(db, row, "accepted" if results else "ignored_unsupported_or_unmapped")
    db.commit()
    for result in results:
        record(
            "webhook_receipt",
            request_id=request.state.request_id,
            receipt_id=result["delivery_id"],
            workspace_id=row.workspace_id,
            status=result["status"],
        )
    return {"status": "accepted", "events": len(results)}


@router.get("/workspaces/{ws}/inbox")
def inbox(ws: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Thread, Contact, Integration, Lead, QualificationConversation)
        .join(Contact, (Contact.id == Thread.contact_id) & (Contact.workspace_id == Thread.workspace_id))
        .join(
            Integration,
            (Integration.id == Thread.integration_id) & (Integration.workspace_id == Thread.workspace_id),
        )
        .join(Lead, (Lead.id == Contact.lead_id) & (Lead.workspace_id == Contact.workspace_id))
        .outerjoin(
            QualificationConversation,
            (QualificationConversation.lead_id == Lead.id)
            & (QualificationConversation.workspace_id == Lead.workspace_id),
        )
        .where(Thread.workspace_id == str(ws))
        .order_by(Thread.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": t.id,
            "lead_id": lead.id,
            "name": lead.name,
            "source": i.kind,
            "mode": "human" if c.opted_out or (conversation and conversation.mode == "human") else t.mode,
            "opted_out": c.opted_out or bool(conversation and conversation.opted_out),
            "last_inbound_at": t.last_inbound_at,
            "active": i.active,
            "summary": lead.summary,
            "score": lead.qualification_score,
            "lead_status": lead.status,
            "can_send": channels.send_gate(db, i, t, c) is None,
        }
        for t, c, i, lead, conversation in rows
    ]


@router.get("/workspaces/{ws}/inbox/{thread_id}/messages")
def messages(ws: UUID, thread_id: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    channels.thread_get(db, ws, thread_id)
    rows = db.scalars(
        select(Message)
        .where(Message.workspace_id == str(ws), Message.thread_id == str(thread_id))
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(200)
    ).all()
    return list(reversed(rows))


@router.post("/workspaces/{ws}/inbox/{thread_id}/control")
def thread_control(
    ws: UUID, thread_id: UUID, body: ThreadControl, membership=Depends(member), db: Session = Depends(get_db)
):
    thread = channels.thread_get(db, ws, thread_id)
    channels.set_control(db, ws, thread, body.mode, body.reason, membership.user_id)
    db.commit()
    return {"mode": thread.mode}


@router.post("/workspaces/{ws}/inbox/{thread_id}/messages", status_code=202)
def manual_message(
    ws: UUID, thread_id: UUID, body: ManualMessage, membership=Depends(member), db: Session = Depends(get_db)
):
    thread = channels.thread_get(db, ws, thread_id)
    channels.lock_related_threads(db, ws, thread)
    key = "human:" + str(thread_id) + ":" + body.request_id
    previous = db.scalar(select(Message).where(Message.workspace_id == str(ws), Message.dedupe_key == key))
    if previous:
        if previous.text != body.text:
            raise HTTPException(409, "Request ID already used for different text")
        return previous
    integration = webhooks.get_integration(db, thread.integration_id, ws)
    contact = db.scalar(
        select(Contact).where(Contact.workspace_id == str(ws), Contact.id == thread.contact_id)
    )
    reason = channels.send_gate(db, integration, thread, contact)
    if reason:
        raise HTTPException(409, reason)
    channels.set_control(db, ws, thread, "human", "Manual reply", membership.user_id)
    message = Message(
        workspace_id=str(ws),
        thread_id=thread.id,
        dedupe_key=key,
        direction="outbound",
        actor_id=membership.user_id,
        text=body.text,
        status="queued",
    )
    db.add(message)
    db.commit()
    return message


@router.post("/workspaces/{ws}/integrations/recover")
def recover(ws: UUID, membership=Depends(admin), db: Session = Depends(get_db)):
    # Explicit operator action, only after stopping/restarting workers. Never resend unknown sends.
    cutoff = now() - timedelta(minutes=10)
    recovered = 0
    for event in db.scalars(
        select(Event)
        .where(Event.workspace_id == str(ws), Event.status == "processing", Event.available_at < cutoff)
        .with_for_update(skip_locked=True)
    ):
        event.status, event.error = "failed", "worker_interrupted_review_before_paid_retry"
        event.processed_at = now()
        recovered += 1
    for message in db.scalars(
        select(Message)
        .where(Message.workspace_id == str(ws), Message.status == "sending", Message.available_at < cutoff)
        .with_for_update(skip_locked=True)
    ):
        message.status, message.error = "unknown", "worker_interrupted_reconcile_with_meta"
        recovered += 1
    db.commit()
    return {"recovered": recovered}
