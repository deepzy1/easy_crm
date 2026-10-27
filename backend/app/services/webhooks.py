"""Verified intake only; durable acceptance precedes qualification or Graph calls."""

import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.config import get_settings
from app.core.security import limiter
from app.models.entities import InboundEvent, Integration, WebhookLog, now, uid
from app.schemas.channels import Envelope, WebsiteLead


EVENT_ID = re.compile(r"^[a-zA-Z0-9_.:-]{1,150}$")


def signing_secret(integration):
    master = get_settings().webhook_master_key.get_secret_value()
    if len(master) < 32:
        raise HTTPException(409, "Set WEBHOOK_MASTER_KEY to at least 32 random characters on the backend")
    return hmac.new(
        master.encode(), f"{integration.id}:{integration.key_version}".encode(), hashlib.sha256
    ).hexdigest()


def get_integration(db, integration_id, ws=None, active=False, lock=False):
    query = select(Integration).where(Integration.id == str(integration_id))
    if ws is not None:
        query = query.where(Integration.workspace_id == str(ws))
    if lock == "key_share":
        # Serialize against explicit integration deactivation/erasure (FOR UPDATE),
        # while remaining compatible with the dispatcher's NO KEY UPDATE policy lock.
        query = query.with_for_update(read=True, key_share=True)
    elif lock:
        query = query.with_for_update()
    row = db.scalar(query)
    if not row or (active and not row.active):
        raise HTTPException(404, "Integration not found or inactive")
    return row


def log(db, integration, result):
    db.add(WebhookLog(workspace_id=integration.workspace_id, integration_id=integration.id, result=result))


def accept(db, integration, event_id, envelope, raw_digest=None):
    data = envelope.model_dump(mode="json")
    # workspace_id is always server-authored; payload_ref points at this minimized receipt.
    data["workspace_id"] = integration.workspace_id
    digest = raw_digest or hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    identity = uid()
    data["payload_ref"] = identity
    data["received_at"] = now().isoformat()
    inserted = db.execute(
        insert(InboundEvent)
        .values(
            id=identity,
            workspace_id=integration.workspace_id,
            integration_id=integration.id,
            external_event_id=event_id,
            payload_hash=digest,
            envelope=data,
            status="pending",
            attempts=0,
            error="",
            available_at=now(),
            received_at=now(),
        )
        .on_conflict_do_nothing(index_elements=["integration_id", "external_event_id"])
        .returning(InboundEvent.id)
    ).scalar()
    if inserted:
        return {"delivery_id": inserted, "status": "accepted"}
    previous = db.scalar(
        select(InboundEvent).where(
            InboundEvent.integration_id == integration.id,
            InboundEvent.external_event_id == event_id,
            InboundEvent.workspace_id == integration.workspace_id,
        )
    )
    if previous.payload_hash != digest:
        raise HTTPException(409, "Event ID was already used for different content")
    return {"delivery_id": previous.id, "status": "duplicate"}


def website_envelope(integration, payload, event_id):
    if not isinstance(payload, dict) or payload.get("event", "lead.created") != "lead.created":
        raise ValueError("Invalid event")
    raw = payload.get("lead", payload.get("form", payload))
    if not isinstance(raw, dict):
        raise ValueError("Invalid lead")
    fields = {key: raw.get(integration.field_map.get(key, key)) for key in WebsiteLead.model_fields}
    contact = WebsiteLead.model_validate({k: v for k, v in fields.items() if v is not None})
    if not (contact.email or contact.phone or contact.external_contact_id):
        raise ValueError("A contact identifier is required")
    occurred = payload.get("occurred_at")
    if occurred:
        occurred = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
    else:
        # Stable on redelivery: only an explicit timestamp is part of normalized identity.
        occurred = datetime.fromtimestamp(0, timezone.utc)
    return Envelope(
        source="website",
        external_contact_id=contact.external_contact_id or contact.email or contact.phone,
        contact=contact,
        text=contact.message,
        occurred_at=occurred,
        kind="lead",
    )


def signed_website(db, integration, raw, headers):
    limiter.check(f"webhook:{integration.id}", 60, 60)
    event_id = headers.get("x-easycrm-event-id", "")
    stamp = headers.get("x-easycrm-timestamp", "")
    supplied = headers.get("x-easycrm-signature", "")
    try:
        if not EVENT_ID.fullmatch(event_id) or abs(time.time() - int(stamp)) > 300:
            raise ValueError()
    except (ValueError, OverflowError):
        raise HTTPException(401, "Invalid or expired webhook timestamp/event ID") from None
    expected = (
        "sha256="
        + hmac.new(
            signing_secret(integration).encode(),
            stamp.encode() + b"." + event_id.encode() + b"." + raw,
            hashlib.sha256,
        ).hexdigest()
    )
    if not hmac.compare_digest(expected.encode(), supplied.encode()):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        envelope = website_envelope(integration, json.loads(raw), event_id)
    except (ValueError, TypeError, ValidationError):
        raise HTTPException(
            422, "Invalid website event; check contact identifiers and field mapping"
        ) from None
    return accept(db, integration, event_id, envelope, hashlib.sha256(raw).hexdigest())


def meta_envelopes(integration, payload):
    """Bounded official text/status/leadgen contracts. Unknown media is ignored."""
    kind, account = integration.kind, integration.external_account_id
    expected_object = {
        "whatsapp": "whatsapp_business_account",
        "meta_leads": "page",
        "instagram": "instagram",
    }[kind]
    if payload.get("object") != expected_object:
        raise ValueError("Unexpected Meta object")
    events = []
    for entry in payload.get("entry", []):
        if kind == "instagram":
            if str(entry.get("id")) != account:
                continue
            for message in entry.get("messaging", []):
                item = message.get("message", {})
                if item.get("is_echo") or not item.get("text"):
                    continue
                sender = str(message["sender"]["id"])
                if str(message.get("recipient", {}).get("id")) != account:
                    continue
                contact = WebsiteLead(name="Instagram prospect", external_contact_id=sender)
                events.append(
                    (
                        item["mid"],
                        Envelope(
                            source=kind,
                            external_contact_id=sender,
                            contact=contact,
                            text=item["text"],
                            occurred_at=datetime.fromtimestamp(
                                int(message["timestamp"]) / 1000, timezone.utc
                            ),
                        ),
                    )
                )
            continue
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if kind == "meta_leads":
                if (
                    change.get("field") != "leadgen"
                    or str(entry.get("id")) != account
                    or str(value.get("page_id")) != account
                ):
                    continue
                identity = str(value["leadgen_id"])
                if not identity.isdigit() or len(identity) > 50:
                    raise ValueError("Invalid lead ID")
                events.append(
                    (
                        identity,
                        Envelope(
                            source=kind,
                            external_contact_id=identity,
                            contact=WebsiteLead(external_contact_id=identity),
                            text="",
                            kind="leadgen",
                            occurred_at=datetime.fromtimestamp(int(value["created_time"]), timezone.utc),
                            metadata={k: str(value[k])[:100] for k in ("form_id", "ad_id") if k in value},
                        ),
                    )
                )
                continue
            if (
                change.get("field") != "messages"
                or str(value.get("metadata", {}).get("phone_number_id")) != account
            ):
                continue
            names = {
                c.get("wa_id"): c.get("profile", {}).get("name", "WhatsApp prospect")
                for c in value.get("contacts", [])
            }
            for message in value.get("messages", []):
                if message.get("type") != "text":
                    continue
                sender = str(message["from"])
                contact = WebsiteLead(name=names.get(sender, "WhatsApp prospect")[:100], phone="+" + sender)
                events.append(
                    (
                        message["id"],
                        Envelope(
                            source=kind,
                            external_contact_id=sender,
                            contact=contact,
                            text=message["text"]["body"],
                            occurred_at=datetime.fromtimestamp(int(message["timestamp"]), timezone.utc),
                        ),
                    )
                )
            for status in value.get("statuses", []):
                state = status.get("status")
                if state not in {"sent", "delivered", "read", "failed"}:
                    continue
                sender = str(status["recipient_id"])
                events.append(
                    (
                        f"{status['id']}:{state}",
                        Envelope(
                            source=kind,
                            external_contact_id=sender,
                            contact=WebsiteLead(phone="+" + sender),
                            text="",
                            kind="status",
                            occurred_at=datetime.fromtimestamp(int(status["timestamp"]), timezone.utc),
                            metadata={
                                "message_id": status["id"],
                                "status": state,
                                "callback_id": str(status.get("biz_opaque_callback_data", ""))[:36],
                            },
                        ),
                    )
                )
    if len(events) > 100 or any(not isinstance(i, str) or not 1 <= len(i) <= 200 for i, _ in events):
        raise ValueError("Too many events or invalid external ID")
    return events
