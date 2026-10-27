"""Durable channel inbox/outbox, conservative policy, and explicit human control."""

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, select, update

from app.core.database import SessionLocal
from app.core.telemetry import record
from app.integrations import meta
from app.models.entities import (
    ChannelContact as Contact,
    ChannelMessage as Message,
    ChannelThread as Thread,
    InboundEvent as Event,
    Integration,
    Lead,
    QualificationConversation as Conversation,
    Stage,
    Workspace,
    now,
)
from app.schemas.channels import WebsiteLead
from app.schemas.qualification import Control
from app.services.qualification import OPTOUT, HUMAN, control_conversation, process_incoming_message


TERMINAL = {"closed", "disqualified"}


def cancel_ai(db, ws, thread_id=None):
    query = update(Message).where(
        Message.workspace_id == str(ws), Message.ai_generated.is_(True), Message.status == "queued"
    )
    if thread_id:
        query = query.where(Message.thread_id == thread_id)
    db.execute(query.values(status="cancelled", error="human_control_changed"))


def thread_get(db, ws, thread_id, lock=False):
    query = select(Thread).where(Thread.workspace_id == str(ws), Thread.id == str(thread_id))
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise HTTPException(404, "Conversation not found")
    return row


def contact_for(db, integration, data, external_id):
    # Workspace lock serializes identity resolution across integrations and workers.
    db.scalar(select(Workspace).where(Workspace.id == integration.workspace_id).with_for_update())
    identities = []
    if data.phone:
        identities.append("phone:" + data.phone)
    if data.email:
        identities.append("email:" + data.email)
    identities.append(f"external:{integration.id}:{external_id}")
    contacts = db.scalars(
        select(Contact).where(
            Contact.workspace_id == integration.workspace_id, Contact.identity.in_(identities)
        )
    ).all()
    lead_ids = {c.lead_id for c in contacts}
    if len(lead_ids) > 1:
        raise HTTPException(409, "Contact identifiers match different leads; human merge required")
    lead = (
        db.scalar(select(Lead).where(Lead.workspace_id == integration.workspace_id, Lead.id.in_(lead_ids)))
        if lead_ids
        else None
    )
    matches = db.scalars(
        select(Lead).where(
            Lead.workspace_id == integration.workspace_id,
            or_(
                Lead.email == data.email if data.email else False,
                Lead.phone == data.phone if data.phone else False,
            ),
        )
    ).all()
    all_leads = lead_ids | {row.id for row in matches}
    if len(all_leads) > 1:
        raise HTTPException(409, "Contact identifiers match different leads; human merge required")
    if not lead and matches:
        lead = matches[0]
    if not lead:
        stage = db.scalar(
            select(Stage.id).where(Stage.workspace_id == integration.workspace_id, Stage.position == 0)
        )
        lead = Lead(
            workspace_id=integration.workspace_id,
            stage_id=stage,
            name=data.name,
            email=data.email,
            phone=data.phone,
            company=data.company,
            source="meta" if integration.kind == "meta_leads" else integration.kind,
        )
        db.add(lead)
        db.flush()
    # Enrich missing contact details while preserving human-edited fields and first source.
    for key in ("email", "phone", "company"):
        if not getattr(lead, key) and getattr(data, key):
            setattr(lead, key, getattr(data, key))
    lead.updated_at = now()
    for identity in identities:
        if not any(c.identity == identity for c in contacts):
            contact = Contact(
                workspace_id=integration.workspace_id,
                lead_id=lead.id,
                identity=identity,
                consent_to_contact=data.consent_to_contact,
                opted_out=any(c.opted_out for c in contacts),
            )
            db.add(contact)
            contacts.append(contact)
    # Do not infer continuing outreach consent from a form or a user-initiated message.
    # Consent only records an explicit true value; opt-out remains sticky on every identity.
    for contact in contacts:
        if data.consent_to_contact and not contact.opted_out:
            contact.consent_to_contact = True
    db.flush()
    return lead, next(c for c in contacts if c.identity == identities[-1])


def apply_status(db, integration, envelope):
    data = envelope["metadata"]
    message = db.scalar(
        select(Message)
        .join(Thread, (Thread.id == Message.thread_id) & (Thread.workspace_id == Message.workspace_id))
        .where(
            Message.workspace_id == integration.workspace_id,
            Thread.integration_id == integration.id,
            Thread.external_contact_id == envelope["external_contact_id"],
            Message.direction == "outbound",
            or_(Message.external_message_id == data["message_id"], Message.id == data.get("callback_id", "")),
        )
        .with_for_update(of=Message)
    )
    if not message:
        return
    rank = {"queued": 0, "sending": 1, "unknown": 1, "failed": 1, "sent": 2, "delivered": 3, "read": 4}
    incoming = data["status"]
    if rank.get(incoming, 0) >= rank.get(message.status, 0):
        message.status = incoming
        message.external_message_id = data["message_id"]
        message.error = "meta_delivery_failed" if incoming == "failed" else ""


async def ingest(db, event, integration):
    envelope = event.envelope
    if not integration.active:
        event.status, event.error = "cancelled", "integration_inactive"
        return
    if envelope["kind"] == "status":
        apply_status(db, integration, envelope)
        event.status = "done"
        return
    if envelope["kind"] == "leadgen":
        details = await meta.fetch_lead(integration, event.external_event_id)
        fields = {f["name"]: f.get("values", [""])[0] for f in details["field_data"] if f.get("values")}
        data = WebsiteLead(
            name=fields.get("full_name", "Facebook prospect"),
            email=fields.get("email", ""),
            phone=fields.get("phone_number", ""),
            external_contact_id=event.external_event_id,
        )
        envelope = {
            **envelope,
            "contact": data.model_dump(),
            "metadata": {
                **envelope["metadata"],
                **{k: str(details[k])[:100] for k in ("ad_id", "form_id", "campaign_id") if k in details},
            },
        }
        event.envelope = envelope
    data = WebsiteLead.model_validate(envelope["contact"])
    lead, contact = contact_for(db, integration, data, envelope["external_contact_id"])
    thread = db.scalar(
        select(Thread).where(
            Thread.workspace_id == integration.workspace_id,
            Thread.integration_id == integration.id,
            Thread.external_contact_id == envelope["external_contact_id"],
        )
    )
    if not thread:
        thread = Thread(
            workspace_id=integration.workspace_id,
            integration_id=integration.id,
            contact_id=contact.id,
            external_contact_id=envelope["external_contact_id"],
            mode="ai" if integration.ai_enabled else "human",
        )
        db.add(thread)
        db.flush()
    text = envelope["text"]
    timestamp = datetime.fromisoformat(envelope["occurred_at"])
    # Only authentic customer messages open a WhatsApp service window; never receipt time.
    if integration.kind == "whatsapp" and text:
        if timestamp > now() + timedelta(minutes=5):
            raise HTTPException(422, "Future customer timestamp rejected")
        if thread.last_inbound_at is None or timestamp > thread.last_inbound_at:
            thread.last_inbound_at = timestamp
    if text:
        message = Message(
            workspace_id=integration.workspace_id,
            thread_id=thread.id,
            dedupe_key="in:" + event.id,
            external_message_id=event.external_event_id,
            direction="inbound",
            text=text,
            status="received",
            created_at=timestamp if timestamp.year > 1970 else now(),
        )
        db.add(message)
    if OPTOUT.search(text):
        for related in db.scalars(
            select(Contact).where(
                Contact.workspace_id == integration.workspace_id, Contact.lead_id == lead.id
            )
        ):
            related.opted_out = True
        for related in db.scalars(
            select(Thread)
            .join(Contact, (Contact.id == Thread.contact_id) & (Contact.workspace_id == Thread.workspace_id))
            .where(Thread.workspace_id == integration.workspace_id, Contact.lead_id == lead.id)
        ):
            related.mode, related.control_version = "human", related.control_version + 1
            cancel_ai(db, integration.workspace_id, related.id)
    elif HUMAN.search(text):
        thread.mode, thread.control_version = "human", thread.control_version + 1
        cancel_ai(db, integration.workspace_id, thread.id)
    event.envelope = {**envelope, "thread_id": thread.id, "lead_id": lead.id}
    event.status = "qualify" if text else "done"


def send_gate(db, integration, thread, contact, *, ai=False, version=None):
    if not integration.active or integration.kind != "whatsapp":
        return "channel_send_unavailable"
    try:
        meta.connection(integration)
    except HTTPException:
        return "meta_not_configured"
    if contact.opted_out:
        return "contact_opted_out"
    if not thread.last_inbound_at or now() >= thread.last_inbound_at + timedelta(hours=24):
        return "service_window_closed_approved_template_required"
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.workspace_id == thread.workspace_id, Conversation.lead_id == contact.lead_id
        )
    )
    if conversation and (conversation.opted_out or conversation.state in TERMINAL):
        return "conversation_closed"
    if ai and (
        not integration.ai_enabled
        or thread.mode != "ai"
        or version != thread.control_version
        or (conversation and conversation.mode != "ai")
    ):
        return "ai_paused_or_control_changed"
    return None


def lock_related_threads(db, ws, thread):
    contact = db.scalar(
        select(Contact).where(Contact.workspace_id == str(ws), Contact.id == thread.contact_id)
    )
    return db.scalars(
        select(Thread)
        .join(Contact, (Contact.id == Thread.contact_id) & (Contact.workspace_id == Thread.workspace_id))
        .where(Thread.workspace_id == str(ws), Contact.lead_id == contact.lead_id)
        .order_by(Thread.id)
        .with_for_update(of=Thread)
    ).all()


def set_control(db, ws, thread, mode, reason, actor):
    # Shared lead ownership avoids one channel resuming automation over another's takeover.
    related = lock_related_threads(db, ws, thread)
    contact = db.scalar(
        select(Contact).where(Contact.workspace_id == str(ws), Contact.id == thread.contact_id)
    )
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.workspace_id == str(ws), Conversation.lead_id == contact.lead_id
        )
    )
    if mode == "ai":
        integration = db.scalar(
            select(Integration).where(
                Integration.workspace_id == str(ws), Integration.id == thread.integration_id
            )
        )
        if not integration.active or not integration.ai_enabled or contact.opted_out:
            raise HTTPException(409, "Enable integration AI policy first; opted-out contacts cannot resume")
        if conversation:
            control_conversation(db, ws, contact.lead_id, Control(action="resume", reason=reason), actor)

    for row in related:
        row.mode, row.control_version = mode, row.control_version + 1
        cancel_ai(db, ws, row.id)
    db.add(
        Message(
            workspace_id=str(ws),
            thread_id=thread.id,
            dedupe_key="control:" + uuid4().hex,
            direction="system",
            actor_id=actor,
            text=f"{mode.capitalize()} mode: {reason}",
            status="recorded",
        )
    )

    if mode == "human" and conversation and conversation.state not in TERMINAL:
        try:
            # NOWAIT inside a savepoint keeps takeover responsive during paid inference.
            with db.begin_nested():
                control_conversation(
                    db, ws, contact.lead_id, Control(action="takeover", reason=reason), actor
                )
        except HTTPException as exc:
            if exc.status_code != 409:
                raise


async def qualify(event_id):
    # Durable claim BEFORE paid inference. A worker crash leaves processing visible for manual recovery.
    with SessionLocal() as db:
        event = db.scalar(
            select(Event)
            .where(Event.id == event_id, Event.status == "qualify")
            .with_for_update(skip_locked=True)
        )
        if not event:
            return
        event.status, event.attempts = "processing", event.attempts + 1
        event.available_at = now()
        db.commit()
    with SessionLocal() as db:
        event = db.get(Event, event_id)
        envelope = event.envelope
        integration = db.scalar(
            select(Integration).where(
                Integration.workspace_id == event.workspace_id, Integration.id == event.integration_id
            )
        )
        thread = thread_get(db, event.workspace_id, envelope["thread_id"])
        version = thread.control_version
        contact = db.scalar(
            select(Contact).where(Contact.workspace_id == event.workspace_id, Contact.id == thread.contact_id)
        )
        try:
            # Save all inbound messages, but do not charge for paused threads.
            if (
                thread.mode != "ai"
                or not integration.ai_enabled
                or not integration.active
                or contact.opted_out
            ) and not (OPTOUT.search(envelope["text"]) or HUMAN.search(envelope["text"])):
                event.status = "done"
                event.processed_at = now()
                db.commit()
                record(
                    "qualification_job",
                    receipt_id=event.id,
                    workspace_id=event.workspace_id,
                    status=event.status,
                )
                return
            plan = await process_incoming_message(
                db,
                event.workspace_id,
                envelope["lead_id"],
                integration.kind,
                event.id,
                envelope["text"],
                datetime.fromisoformat(envelope["occurred_at"]),
                share_conversation=True,
            )
            # Replayed historical plans are never dispatched.
            if plan.reply and plan.mode == "ai" and not plan.duplicate and integration.kind == "whatsapp":
                db.add(
                    Message(
                        workspace_id=event.workspace_id,
                        thread_id=thread.id,
                        dedupe_key="ai:" + event.id,
                        direction="outbound",
                        text="Automated assistant: " + plan.reply,
                        status="queued",
                        ai_generated=True,
                        control_version=version,
                    )
                )
            db.refresh(thread)
            if thread.mode == "human" and plan.mode == "ai" and plan.state not in TERMINAL:
                control_conversation(
                    db,
                    event.workspace_id,
                    envelope["lead_id"],
                    Control(action="takeover", reason="Channel human takeover superseded this inference"),
                    None,
                )
            event.status, event.error = "done", ""
            event.processed_at = now()
            db.commit()
            record(
                "qualification_job", receipt_id=event.id, workspace_id=event.workspace_id, status=event.status
            )
        except Exception as exc:
            db.rollback()
            event = db.get(Event, event_id)
            # Authored codes only: provider bodies, PII and credentials never enter delivery logs.
            from app.ai.providers import ProviderError

            event.status = "failed"
            event.processed_at = now()
            event.error = (
                exc.code
                if isinstance(exc, ProviderError)
                else "qualification_failed_review_settings_or_rules"
            )
            db.commit()
            record(
                "qualification_job",
                receipt_id=event.id,
                workspace_id=event.workspace_id,
                status=event.status,
                error=event.error,
            )


async def dispatch(message_id):
    with SessionLocal() as db:
        message = db.scalar(
            select(Message).where(
                Message.id == message_id, Message.status == "queued", Message.available_at <= now()
            )
        )
        if not message:
            return
        # Thread lock serializes takeover against the final gate + actual HTTP dispatch.
        thread = thread_get(db, message.workspace_id, message.thread_id, lock=True)
        db.refresh(message, with_for_update=True)
        if message.status != "queued":
            return
        integration = db.scalar(
            select(Integration).where(
                Integration.workspace_id == thread.workspace_id, Integration.id == thread.integration_id
            )
        )
        contact = db.scalar(
            select(Contact).where(
                Contact.workspace_id == thread.workspace_id, Contact.id == thread.contact_id
            )
        )
        # Canonical core controls also serialize with the final send.
        db.scalar(
            select(Lead)
            .where(Lead.workspace_id == thread.workspace_id, Lead.id == contact.lead_id)
            .with_for_update()
        )
        reason = send_gate(
            db, integration, thread, contact, ai=message.ai_generated, version=message.control_version
        )
        if reason:
            message.status, message.error = "cancelled", reason
            db.commit()
            return
        try:
            meta.connection(integration)
        except HTTPException:
            message.status, message.error = "failed", "meta_not_configured"
            db.commit()
            return
        message.status, message.attempts = "sending", message.attempts + 1
        message.available_at = now()
        db.commit()
    # Sending marker survives crashes; don't automatically retry ambiguous outcomes.
    with SessionLocal() as db:
        message = db.get(Message, message_id)
        integration = db.scalar(
            select(Integration)
            .join(
                Thread,
                (Thread.integration_id == Integration.id) & (Thread.workspace_id == Integration.workspace_id),
            )
            .where(Thread.workspace_id == message.workspace_id, Thread.id == message.thread_id)
            # NO KEY UPDATE protects policy while permitting FK KEY SHARE locks
            # from new durable webhook receipts during the network request.
            .with_for_update(of=Integration, key_share=True)
        )
        thread = thread_get(db, message.workspace_id, message.thread_id, lock=True)
        contact = db.scalar(
            select(Contact)
            .where(Contact.workspace_id == thread.workspace_id, Contact.id == thread.contact_id)
            .with_for_update()
        )
        db.scalar(
            select(Lead)
            .where(Lead.workspace_id == thread.workspace_id, Lead.id == contact.lead_id)
            .with_for_update()
        )
        reason = send_gate(
            db, integration, thread, contact, ai=message.ai_generated, version=message.control_version
        )
        if reason:
            message.status, message.error = "cancelled", reason
            db.commit()
            return
        try:
            external_id = await meta.send_text(
                integration, thread.external_contact_id, message.text, message.id
            )
            # Conditional SQL updates preserve a concurrently received delivery/read receipt.
            db.execute(
                update(Message)
                .where(Message.id == message.id, Message.status.in_(["sending", "unknown"]))
                .values(status="sent", error="")
            )
            db.execute(
                update(Message).where(Message.id == message.id).values(external_message_id=external_id)
            )
        except meta.MetaError as exc:
            state = "unknown" if exc.ambiguous else "failed"
            due = now()
            if exc.retryable and message.attempts < 5:
                state = "queued"
                due = now() + timedelta(seconds=min(900, 5 * 2**message.attempts))
            db.execute(
                update(Message)
                .where(Message.id == message.id, Message.status == "sending")
                .values(status=state, error=exc.code, available_at=due)
            )
        except Exception:
            db.execute(
                update(Message)
                .where(Message.id == message.id, Message.status == "sending")
                .values(status="unknown", error="delivery_outcome_unknown_review_before_retry")
            )
        db.commit()


async def run_once():
    with SessionLocal() as db:
        event = db.scalar(
            select(Event)
            .where(Event.status == "pending", Event.available_at <= now())
            .order_by(Event.received_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if event:
            identity = event.id
            event.attempts += 1
            integration = db.scalar(
                select(Integration).where(
                    Integration.workspace_id == event.workspace_id, Integration.id == event.integration_id
                )
            )
            try:
                with db.begin_nested():
                    await ingest(db, event, integration)
            except meta.MetaError as exc:
                event = db.get(Event, identity)
                event.error = exc.code
                event.status = "pending" if exc.retryable and event.attempts < 5 else "failed"
                event.available_at = now() + timedelta(seconds=5 * 2**event.attempts)
            except Exception:
                event = db.get(Event, identity)
                event.status, event.error = "failed", "ingestion_failed_check_contact_or_mapping"
            if event.status in {"done", "cancelled", "failed"}:
                event.processed_at = now()
            db.commit()
            record(
                "intake_job",
                receipt_id=event.id,
                workspace_id=event.workspace_id,
                status=event.status,
                attempts=event.attempts,
                error=event.error,
            )
    with SessionLocal() as db:
        identity = db.scalar(
            select(Event.id).where(Event.status == "qualify").order_by(Event.received_at).limit(1)
        )
    if identity:
        await qualify(identity)
    with SessionLocal() as db:
        identity = db.scalar(
            select(Message.id)
            .where(Message.direction == "outbound", Message.status == "queued", Message.available_at <= now())
            .order_by(Message.created_at)
            .limit(1)
        )
    if identity:
        await dispatch(identity)
