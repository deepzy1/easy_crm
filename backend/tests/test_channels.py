"""Real PostgreSQL contracts. Only inference and Meta transport use fixtures."""

import asyncio
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from conftest import account
from app.core.config import MetaConnection, get_settings
from app.core.database import SessionLocal
from app.integrations import meta
from app.models.entities import (
    ChannelMessage,
    ChannelThread,
    InboundEvent,
    Lead,
    Membership,
    QualificationConversation,
    now,
)
from app.services import channels
from app.services.qualification import examples


@pytest.fixture(autouse=True)
def channel_settings(monkeypatch):
    monkeypatch.setattr(
        get_settings(), "webhook_master_key", SecretStr("fictional-test-master-key-32-characters-only")
    )
    monkeypatch.setattr(get_settings(), "meta_connections", {})


def integration(client, owner, kind="website", ai=False, field_map=None):
    headers, ws = owner
    if kind != "website":
        get_settings().meta_connections["test-" + ws] = MetaConnection(
            workspace_id=ws,
            kind=kind,
            external_account_id="1234567890",
            app_secret="fictional-app-secret",
            verify_token="fictional-verify-token",
            access_token="fictional-access-token",
        )
    result = client.post(
        f"/api/v1/workspaces/{ws}/integrations",
        headers=headers,
        json={
            "name": "Fictional channel",
            "kind": kind,
            "ai_enabled": ai,
            "field_map": field_map or {},
            "credential_alias": "" if kind == "website" else "test-" + ws,
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def website(client, item, event="event-1", payload=None, secret=None, stamp=None):
    payload = payload or {
        "lead": {
            "name": "Fictional prospect",
            "phone": "+919876543210",
            "email": "prospect@example.com",
            "message": "Hello",
        }
    }
    raw = json.dumps(payload).encode()
    stamp = str(stamp if stamp is not None else int(time.time()))
    signature = (
        "sha256="
        + hmac.new(
            (secret or item["signing_secret"]).encode(),
            stamp.encode() + b"." + event.encode() + b"." + raw,
            hashlib.sha256,
        ).hexdigest()
    )
    return client.post(
        item["webhook_url"],
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-EasyCRM-Event-ID": event,
            "X-EasyCRM-Timestamp": stamp,
            "X-EasyCRM-Signature": signature,
        },
    )


def wa(text="Hello", identity="wamid.test-1", timestamp=None):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "999",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": "1234567890"},
                            "contacts": [
                                {"wa_id": "919876543210", "profile": {"name": "Fictional WhatsApp prospect"}}
                            ],
                            "messages": [
                                {
                                    "id": identity,
                                    "from": "919876543210",
                                    "timestamp": str(timestamp or int(time.time())),
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def meta_event(client, item, payload):
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"fictional-app-secret", raw, hashlib.sha256).hexdigest()
    return client.post(
        item["webhook_url"],
        content=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": signature},
    )


def tick():
    asyncio.run(channels.run_once())


def inbox(client, owner):
    return client.get(f"/api/v1/workspaces/{owner[1]}/inbox", headers=owner[0]).json()


def prepare_ai(client, owner, monkeypatch):
    headers, ws = owner
    body = {**examples()["generic_b2b"], "activate": True}
    assert (
        client.post(
            f"/api/v1/workspaces/{ws}/qualification/templates", headers=headers, json=body
        ).status_code
        == 201
    )
    from app.models.entities import ModelPreference

    with SessionLocal() as db:
        db.add(ModelPreference(workspace_id=ws, provider="nvidia", model="nvidia/nemotron-3-ultra-550b-a55b"))
        db.commit()
    calls = []

    async def fixture(*args, **kwargs):
        calls.append(args)
        return {
            "text": '{"fields": [], "quotes": [], "needs_human": false}',
            "provider": "nvidia",
            "model": args[3],
            "latency_ms": 1,
        }

    monkeypatch.setattr("app.services.qualification.execute", fixture)
    return calls


def test_website_signed_durable_duplicate_conflict_rotation_revoke(client, owner):
    item = integration(client, owner)
    assert website(client, item).status_code == 202
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead)) == 0
    assert website(client, item).json()["status"] == "duplicate"
    assert website(client, item, payload={"lead": {"email": "other@example.com"}}).status_code == 409
    assert website(client, item, event="old", stamp=int(time.time()) - 400).status_code == 401
    assert website(client, item, event="bad", secret="wrong").status_code == 401
    tick()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead)) == 1
        assert db.scalar(select(func.count()).select_from(ChannelMessage)) == 1
    headers, ws = owner
    rotated = client.post(f"/api/v1/workspaces/{ws}/integrations/{item['id']}/rotate", headers=headers).json()
    assert website(client, item, event="after-rotate").status_code == 401
    item["signing_secret"] = rotated["signing_secret"]
    assert website(client, item, event="after-rotate").status_code == 202
    client.patch(
        f"/api/v1/workspaces/{ws}/integrations/{item['id']}",
        headers=headers,
        json={"active": False, "ai_enabled": False},
    )
    assert website(client, item, event="revoked").status_code == 404
    assert (
        rotated["signing_secret"]
        not in client.get(f"/api/v1/workspaces/{ws}/integrations", headers=headers).text
    )


def test_mapping_and_payload_cannot_choose_workspace(client, owner):
    item = integration(
        client, owner, field_map={"name": "full_name", "phone": "mobile", "message": "enquiry"}
    )
    assert (
        website(
            client,
            item,
            payload={
                "workspace_id": "attacker",
                "form": {"full_name": "Mapped person", "mobile": "+91 98765 43210", "enquiry": "Help"},
            },
        ).status_code
        == 202
    )
    tick()
    with SessionLocal() as db:
        lead = db.scalar(select(Lead))
        assert (lead.name, lead.phone, lead.workspace_id) == ("Mapped person", "+919876543210", owner[1])
        event = db.scalar(select(InboundEvent))
        assert event.envelope["workspace_id"] == owner[1]
        assert "attacker" not in json.dumps(event.envelope)


@pytest.mark.parametrize(
    "lead", [{"message": "no identifier"}, {"phone": "9876543210"}, {"email": "invalid"}]
)
def test_invalid_contacts(client, owner, lead):
    assert website(client, integration(client, owner), payload={"lead": lead}).status_code == 422


def test_website_limits(client, owner):
    item = integration(client, owner)
    assert (
        website(
            client, item, payload={"lead": {"email": "a@example.com", "message": "x" * 66000}}
        ).status_code
        == 413
    )
    from app.core.security import limiter

    for _ in range(60):
        limiter.check(f"webhook:{item['id']}", 60, 60)
    assert website(client, item).status_code == 429


def test_cross_workspace_identity_and_authorization(client, owner):
    one = integration(client, owner)
    other = account(client, email="other@example.com", workspace="Other workspace")
    two = integration(client, other)
    assert website(client, one).status_code == website(client, two).status_code == 202
    tick()
    tick()
    with SessionLocal() as db:
        leads = db.scalars(select(Lead)).all()
        assert len(leads) == 2 and len({lead.workspace_id for lead in leads}) == 2
        thread_id = db.scalar(select(ChannelThread.id).where(ChannelThread.workspace_id == owner[1]))
    assert client.get(f"/api/v1/workspaces/{owner[1]}/integrations", headers=other[0]).status_code == 404
    assert (
        client.get(f"/api/v1/workspaces/{other[1]}/inbox/{thread_id}/messages", headers=other[0]).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/workspaces/{other[1]}/integrations/{one['id']}/rotate", headers=other[0]
        ).status_code
        == 404
    )


def test_meta_alias_cannot_be_claimed_by_other_workspace(client, owner):
    integration(client, owner, "whatsapp")
    other = account(client, email="other@example.com")
    response = client.post(
        f"/api/v1/workspaces/{other[1]}/integrations",
        headers=other[0],
        json={"name": "Claim", "kind": "whatsapp", "credential_alias": "test-" + owner[1]},
    )
    assert response.status_code == 422
    assert "fictional-access-token" not in response.text
    assert (
        "test-" + owner[1]
        not in client.get(f"/api/v1/workspaces/{other[1]}/integrations", headers=other[0]).text
    )


def test_meta_challenge_signature_account_mapping_and_dedup(client, owner):
    item = integration(client, owner, "whatsapp")
    challenge = client.get(
        item["webhook_url"],
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "fictional-verify-token",
            "hub.challenge": "987654",
        },
    )
    assert challenge.status_code == 200 and challenge.text == "987654"
    assert (
        client.get(
            item["webhook_url"], params={"hub.mode": "subscribe", "hub.verify_token": "bad"}
        ).status_code
        == 403
    )
    assert client.post(item["webhook_url"], json=wa()).status_code == 401
    payload = wa()
    assert (
        meta_event(client, item, payload).status_code == meta_event(client, item, payload).status_code == 200
    )
    ignored = wa(identity="wrong-account")
    ignored["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "666"
    assert meta_event(client, item, ignored).json()["events"] == 0
    tick()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(InboundEvent)) == 1
        assert db.scalar(select(func.count()).select_from(ChannelMessage)) == 1


def test_whatsapp_qualifies_sends_with_saved_model(client, owner, monkeypatch):
    calls = prepare_ai(client, owner, monkeypatch)
    sent = []

    async def send(*args):
        sent.append(args)
        return "wamid.outbound"

    monkeypatch.setattr(meta, "send_text", send)
    item = integration(client, owner, "whatsapp", ai=True)
    payload = wa()
    assert meta_event(client, item, payload).status_code == 200
    tick()
    assert len(calls) == len(sent) == 1
    with SessionLocal() as db:
        messages = db.scalars(select(ChannelMessage).order_by(ChannelMessage.created_at)).all()
        assert [m.direction for m in messages] == ["inbound", "outbound"]
        assert messages[-1].status == "sent" and messages[-1].text.startswith("Automated assistant:")
        assert db.scalar(select(QualificationConversation)).channel == "whatsapp"
    meta_event(client, item, payload)
    tick()
    assert len(calls) == len(sent) == 1


def test_takeover_while_inference_running_prevents_send(client, owner, monkeypatch):
    prepare_ai(client, owner, monkeypatch)
    item = integration(client, owner, "whatsapp", ai=True)
    sent = []

    async def forbidden(*args):
        sent.append(args)
        return "should-not-send"

    monkeypatch.setattr(meta, "send_text", forbidden)

    async def infer(*args, **kwargs):
        thread = inbox(client, owner)[0]
        response = client.post(
            f"/api/v1/workspaces/{owner[1]}/inbox/{thread['id']}/control",
            headers=owner[0],
            json={"mode": "human", "reason": "Take over while inference runs"},
        )
        assert response.status_code == 200, response.text
        return {"text": '{"fields": []}', "provider": "nvidia", "model": args[3]}

    monkeypatch.setattr("app.services.qualification.execute", infer)
    meta_event(client, item, wa())
    tick()
    assert sent == []
    with SessionLocal() as db:
        outgoing = db.scalar(select(ChannelMessage).where(ChannelMessage.direction == "outbound"))
        assert outgoing.status == "cancelled" and outgoing.error == "ai_paused_or_control_changed"
    meta_event(client, item, wa(identity="wamid.after-takeover"))
    tick()
    assert sent == []


def test_manual_reply_idempotency_window_and_optout(client, owner, monkeypatch):
    item = integration(client, owner, "whatsapp")
    meta_event(client, item, wa())
    tick()
    thread = inbox(client, owner)[0]
    path = f"/api/v1/workspaces/{owner[1]}/inbox/{thread['id']}/messages"
    body = {"request_id": "manual-1", "text": "Human reply"}
    response = client.post(path, headers=owner[0], json=body)
    assert response.status_code == 202, response.text
    assert client.post(path, headers=owner[0], json=body).json()["id"] == response.json()["id"]
    assert client.post(path, headers=owner[0], json={**body, "text": "Changed"}).status_code == 409
    with SessionLocal() as db:
        db.get(ChannelThread, thread["id"]).last_inbound_at = now() - timedelta(hours=25)
        db.commit()
    assert client.post(path, headers=owner[0], json={**body, "request_id": "outside"}).status_code == 409

    async def never(*args):
        pytest.fail("Outside-window send")

    monkeypatch.setattr(meta, "send_text", never)
    tick()
    meta_event(client, item, wa(text="STOP", identity="wamid.stop"))
    tick()
    assert inbox(client, owner)[0]["opted_out"] is True
    assert client.post(path, headers=owner[0], json={**body, "request_id": "optout"}).status_code == 409


def test_inference_failure_keeps_inbound_requires_explicit_retry(client, owner, monkeypatch):
    calls = prepare_ai(client, owner, monkeypatch)
    from app.ai.providers import ProviderError

    async def failure(*args, **kwargs):
        calls.append(args)
        raise ProviderError("provider_unavailable", "safe message", 503)

    monkeypatch.setattr("app.services.qualification.execute", failure)
    item = integration(client, owner, "whatsapp", ai=True)
    meta_event(client, item, wa())
    tick()
    tick()
    with SessionLocal() as db:
        event = db.scalar(select(InboundEvent))
        assert event.status == "failed" and event.error == "provider_unavailable"
        assert db.scalar(select(func.count()).select_from(ChannelMessage)) == 1
        identity = event.id
    assert len(calls) == 1
    assert (
        client.post(
            f"/api/v1/workspaces/{owner[1]}/integrations/deliveries/{identity}/retry", headers=owner[0]
        ).status_code
        == 200
    )
    tick()
    assert len(calls) == 2


@pytest.mark.parametrize(
    "ambiguous,retryable,expected",
    [(True, False, "unknown"), (False, True, "queued"), (False, False, "failed")],
)
def test_outbox_retry_and_ambiguous_outcomes(client, owner, monkeypatch, ambiguous, retryable, expected):
    item = integration(client, owner, "whatsapp")
    meta_event(client, item, wa())
    tick()
    thread = inbox(client, owner)[0]
    result = client.post(
        f"/api/v1/workspaces/{owner[1]}/inbox/{thread['id']}/messages",
        headers=owner[0],
        json={"request_id": "reply", "text": "Hello"},
    )
    assert result.status_code == 202
    attempts = []

    async def fail(*args):
        attempts.append(args)
        raise meta.MetaError("authored_failure", ambiguous=ambiguous, retryable=retryable)

    monkeypatch.setattr(meta, "send_text", fail)
    tick()
    tick()
    with SessionLocal() as db:
        row = db.get(ChannelMessage, result.json()["id"])
        assert row.status == expected and row.attempts == 1
    assert len(attempts) == 1


def test_status_reconciles_unknown_and_does_not_regress(client, owner):
    item = integration(client, owner, "whatsapp")
    meta_event(client, item, wa())
    tick()
    thread = inbox(client, owner)[0]
    result = client.post(
        f"/api/v1/workspaces/{owner[1]}/inbox/{thread['id']}/messages",
        headers=owner[0],
        json={"request_id": "reply", "text": "Hello"},
    ).json()
    with SessionLocal() as db:
        db.get(ChannelMessage, result["id"]).status = "unknown"
        db.commit()
    for state in ["read", "delivered", "sent", "failed"]:
        payload = wa()
        value = payload["entry"][0]["changes"][0]["value"]
        value.pop("messages")
        value["statuses"] = [
            {
                "id": "wamid.sent",
                "recipient_id": "919876543210",
                "status": state,
                "timestamp": str(int(time.time())),
                "biz_opaque_callback_data": result["id"],
            }
        ]
        assert meta_event(client, item, payload).status_code == 200
        tick()
    with SessionLocal() as db:
        assert db.get(ChannelMessage, result["id"]).status == "read"


def test_facebook_and_instagram_fixture_contracts(client, owner, monkeypatch):
    item = integration(client, owner, "meta_leads")
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "1234567890",
                "changes": [
                    {
                        "field": "leadgen",
                        "value": {
                            "leadgen_id": "555",
                            "page_id": "1234567890",
                            "created_time": int(time.time()),
                            "form_id": "777",
                        },
                    }
                ],
            }
        ],
    }
    calls = []

    async def fetch(config, method, path, **kwargs):
        calls.append((method, path))
        return {
            "id": "555",
            "campaign_id": "333",
            "field_data": [
                {"name": "full_name", "values": ["Facebook fixture"]},
                {"name": "email", "values": ["facebook@example.com"]},
            ],
        }

    monkeypatch.setattr(meta, "graph", fetch)
    assert meta_event(client, item, payload).status_code == 200
    tick()
    assert calls == [("GET", "555")]
    with SessionLocal() as db:
        assert db.scalar(select(Lead)).name == "Facebook fixture"
        assert db.scalar(select(InboundEvent)).envelope["metadata"]["campaign_id"] == "333"
    ig = integration(client, owner, "instagram")
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "1234567890",
                "messaging": [
                    {
                        "sender": {"id": "888"},
                        "recipient": {"id": "1234567890"},
                        "timestamp": int(time.time() * 1000),
                        "message": {"mid": "ig.mid.1", "text": "Instagram fixture"},
                    }
                ],
            }
        ],
    }
    assert meta_event(client, ig, payload).status_code == 200
    tick()
    assert next(t for t in inbox(client, owner) if t["source"] == "instagram")["can_send"] is False

    # Channel source attribution must remain readable through the existing CRM DTO.
    leads = client.get(f"/api/v1/workspaces/{owner[1]}/leads", headers=owner[0])
    assert leads.status_code == 200
    assert {lead["source"] for lead in leads.json()["items"]} == {"meta", "instagram"}


def test_roles_and_compound_foreign_keys(client, owner):
    item = integration(client, owner)
    website(client, item)
    tick()
    other = account(client, email="member@example.com")
    with SessionLocal() as db:
        user_id = db.scalar(select(Membership.user_id).where(Membership.workspace_id == other[1]))
        db.add(Membership(workspace_id=owner[1], user_id=user_id, role="salesperson"))
        db.commit()
        thread = db.scalar(select(ChannelThread))
        db.add(
            ChannelMessage(
                workspace_id=other[1],
                thread_id=thread.id,
                dedupe_key="cross",
                direction="inbound",
                text="cross",
                status="received",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    assert client.get(f"/api/v1/workspaces/{owner[1]}/integrations", headers=other[0]).status_code == 403
    assert client.get(f"/api/v1/workspaces/{owner[1]}/inbox", headers=other[0]).status_code == 200


def test_concurrent_signed_receipts_create_one_lead(client, owner):
    item = integration(client, owner)
    from fastapi.testclient import TestClient
    from app.main import app

    def receive(_):
        with TestClient(app) as independent:
            return website(independent, item).status_code

    with ThreadPoolExecutor(max_workers=3) as pool:
        assert list(pool.map(receive, range(3))) == [202, 202, 202]
    tick()
    tick()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(InboundEvent)) == 1
        assert db.scalar(select(func.count()).select_from(Lead)) == 1


@pytest.mark.parametrize(
    "status,retryable,ambiguous",
    [(429, True, False), (503, False, True), (401, False, False), (400, False, False)],
)
def test_graph_transport_safe_failures(monkeypatch, status, retryable, ambiguous):
    config = MetaConnection(
        workspace_id="test",
        kind="whatsapp",
        external_account_id="123",
        app_secret="secret",
        verify_token="verify",
        access_token="access",
    )
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"error": {"message": "RAW SECRET MUST NOT ESCAPE"}})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )
    with pytest.raises(meta.MetaError) as caught:
        asyncio.run(meta.graph(config, "POST", "123/messages", body={"text": "test"}))
    assert caught.value.retryable == retryable and caught.value.ambiguous == ambiguous
    assert "RAW SECRET" not in str(caught.value)
    assert requests[0].url.host == "graph.facebook.com"
    assert requests[0].headers["authorization"] == "Bearer access"
    assert "access" not in str(requests[0].url)


def test_two_workers_never_dispatch_same_outbox_twice(client, owner, monkeypatch):
    item = integration(client, owner, "whatsapp")
    meta_event(client, item, wa())
    tick()
    thread = inbox(client, owner)[0]
    result = client.post(
        f"/api/v1/workspaces/{owner[1]}/inbox/{thread['id']}/messages",
        headers=owner[0],
        json={"request_id": "concurrent", "text": "Exactly one attempt"},
    ).json()
    sent = []

    async def send(*args):
        sent.append(args)
        await asyncio.sleep(0.05)
        return "wamid.only-once"

    monkeypatch.setattr(meta, "send_text", send)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: asyncio.run(channels.dispatch(result["id"])), range(2)))
    assert len(sent) == 1
    with SessionLocal() as db:
        message = db.get(ChannelMessage, result["id"])
        assert message.status == "sent" and message.attempts == 1


def test_retry_backoff_succeeds_without_duplicate_records(client, owner, monkeypatch):
    item = integration(client, owner, "whatsapp")
    meta_event(client, item, wa())
    tick()
    thread = inbox(client, owner)[0]
    result = client.post(
        f"/api/v1/workspaces/{owner[1]}/inbox/{thread['id']}/messages",
        headers=owner[0],
        json={"request_id": "retry", "text": "Retry after rejection"},
    ).json()
    attempts = []

    async def send(*args):
        attempts.append(args)
        if len(attempts) == 1:
            raise meta.MetaError("meta_rate_limited", retryable=True)
        return "wamid.accepted"

    monkeypatch.setattr(meta, "send_text", send)
    tick()
    with SessionLocal() as db:
        message = db.get(ChannelMessage, result["id"])
        assert message.status == "queued" and message.available_at > now()
        message.available_at = now() - timedelta(seconds=1)
        db.commit()
    tick()
    assert len(attempts) == 2
    with SessionLocal() as db:
        message = db.get(ChannelMessage, result["id"])
        assert message.status == "sent" and message.attempts == 2
        assert (
            db.scalar(
                select(func.count()).select_from(ChannelMessage).where(ChannelMessage.direction == "outbound")
            )
            == 1
        )


def test_website_qualification_never_contacts_form_submitter(client, owner, monkeypatch):
    calls = prepare_ai(client, owner, monkeypatch)
    item = integration(client, owner, ai=True)
    website(client, item)
    tick()
    assert len(calls) == 1
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(ChannelMessage).where(ChannelMessage.direction == "outbound")
            )
            == 0
        )


def test_recovery_marks_interrupted_work_without_resending(client, owner):
    item = integration(client, owner)
    website(client, item)
    tick()
    with SessionLocal() as db:
        event = db.scalar(select(InboundEvent))
        event.status, event.available_at = "processing", now() - timedelta(minutes=11)
        db.commit()
    response = client.post(f"/api/v1/workspaces/{owner[1]}/integrations/recover", headers=owner[0])
    assert response.status_code == 200 and response.json()["recovered"] == 1
    with SessionLocal() as db:
        assert db.scalar(select(InboundEvent)).status == "failed"


def test_qualification_controls_cancel_channel_ai_even_after_resuming(client, owner, monkeypatch):
    prepare_ai(client, owner, monkeypatch)
    item = integration(client, owner, "whatsapp", ai=True)
    meta_event(client, item, wa())
    # Leave the outbox queued so the existing CRM control route can supersede it.
    original_dispatch = channels.dispatch

    async def deferred(_):
        return

    monkeypatch.setattr(channels, "dispatch", deferred)
    tick()
    thread = inbox(client, owner)[0]
    path = f"/api/v1/workspaces/{owner[1]}/leads/{thread['lead_id']}/qualification/control"
    for action in ("takeover", "resume"):
        response = client.post(
            path, headers=owner[0], json={"action": action, "reason": "CRM human control audit"}
        )
        assert response.status_code == 200, response.text
    with SessionLocal() as db:
        outgoing = db.scalar(select(ChannelMessage).where(ChannelMessage.direction == "outbound"))
        assert outgoing.status == "cancelled"
        message_id = outgoing.id
    monkeypatch.setattr(channels, "dispatch", original_dispatch)

    async def forbidden(*args):
        pytest.fail("Stale AI message must stay cancelled after resume")

    monkeypatch.setattr(meta, "send_text", forbidden)
    asyncio.run(original_dispatch(message_id))


def test_retention_redacts_pii_but_retains_duplicate_defense(client, owner):
    item = integration(client, owner)
    website(client, item)
    tick()
    from app.channel_maintenance import purge

    with SessionLocal() as db:
        event = db.scalar(select(InboundEvent))
        event.received_at = now() - timedelta(days=31)
        db.commit()
        purge(db)
        db.refresh(event)
        assert event.envelope == {"redacted": True}
        assert event.payload_hash
    assert website(client, item).json()["status"] == "duplicate"
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead)) == 1


def test_meta_intake_acknowledges_during_outbound_http_call(client, owner, monkeypatch):
    item = integration(client, owner, "whatsapp")
    meta_event(client, item, wa())
    tick()
    thread = inbox(client, owner)[0]
    queued = client.post(
        f"/api/v1/workspaces/{owner[1]}/inbox/{thread['id']}/messages",
        headers=owner[0],
        json={"request_id": "ack", "text": "Outbound reply"},
    ).json()

    async def send(*args):
        # Dispatch holds policy locks. Durable public intake must not wait on Graph I/O.
        response = meta_event(client, item, wa(identity="wamid.concurrent-inbound"))
        assert response.status_code == 200, response.text
        return "wamid.outgoing"

    monkeypatch.setattr(meta, "send_text", send)
    asyncio.run(channels.dispatch(queued["id"]))
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(InboundEvent)) == 2
        assert db.get(ChannelMessage, queued["id"]).status == "sent"


def test_new_event_enriches_same_contact_without_overwriting_human_fields(client, owner):
    item = integration(client, owner)
    website(
        client,
        item,
        payload={
            "lead": {"name": "Original name", "email": "person@example.com", "message": "First enquiry"}
        },
    )
    tick()
    website(
        client,
        item,
        event="second",
        payload={
            "lead": {
                "name": "Incoming different name",
                "email": "PERSON@example.com",
                "phone": "+919876543210",
                "company": "New company",
                "message": "Second enquiry",
            }
        },
    )
    tick()
    with SessionLocal() as db:
        leads = db.scalars(select(Lead)).all()
        assert len(leads) == 1
        assert leads[0].name == "Original name"
        assert leads[0].phone == "+919876543210" and leads[0].company == "New company"
        assert db.scalar(select(func.count()).select_from(ChannelMessage)) == 2


def test_conflicting_crm_identity_fails_instead_of_merging_people(client, owner):
    headers, ws = owner
    for data in (
        {"name": "Email person", "email": "person@example.com"},
        {"name": "Phone person", "phone": "+919876543210"},
    ):
        assert client.post(f"/api/v1/workspaces/{ws}/leads", headers=headers, json=data).status_code == 201
    item = integration(client, owner)
    website(client, item, payload={"lead": {"email": "person@example.com", "message": "First enquiry"}})
    tick()
    website(
        client,
        item,
        event="conflicting",
        payload={"lead": {"email": "person@example.com", "phone": "+919876543210"}},
    )
    tick()
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Lead)) == 2
        assert (
            db.scalar(select(InboundEvent).where(InboundEvent.external_event_id == "conflicting")).status
            == "failed"
        )
