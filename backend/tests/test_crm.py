from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.models.entities import AuthSession, Lead, Membership, User, now
from conftest import account


def path(ws, tail=""):
    return f"/api/v1/workspaces/{ws}{tail}"


def test_register_password_session_and_logout(client, owner):
    headers, ws = owner
    assert ws
    with SessionLocal() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")
        assert "Test-password" not in user.password_hash
        session = db.scalar(select(AuthSession))
        assert session.token_hash != headers["Authorization"][7:]
    cookie = client.cookies.get("easycrm_session")
    assert cookie
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_login_duplicate_invalid_and_expired_session(client, owner):
    headers, _ = owner
    duplicate = client.post(
        "/api/v1/auth/register",
        json={
            "email": "alex@example.com",
            "name": "Alex",
            "password": "Test-password-123!",
            "workspace_name": "Duplicate",
        },
    )
    assert duplicate.status_code == 409
    for email in ("alex@example.com", "missing@example.com"):
        assert (
            client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"}).status_code == 401
        )
    success = client.post(
        "/api/v1/auth/login", json={"email": "ALEX@example.com", "password": "Test-password-123!"}
    )
    assert success.status_code == 200
    assert "HttpOnly" in success.headers["set-cookie"] and "SameSite=strict" in success.headers["set-cookie"]
    with SessionLocal() as db:
        for session in db.scalars(select(AuthSession)):
            session.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_validation_does_not_echo_password(client):
    secret = "short!"
    result = client.post(
        "/api/v1/auth/register",
        json={"email": "invalid", "password": secret, "name": "", "workspace_name": ""},
    )
    assert result.status_code == 422
    assert secret not in result.text
    assert result.json()["error"]["request_id"]


def test_cookie_origin_csrf_and_cors(client, owner):
    result = client.post(
        "/api/v1/workspaces", json={"name": "Blocked"}, headers={"Origin": "https://evil.example"}
    )
    assert result.status_code == 403
    client.headers.pop("Origin")
    assert client.post("/api/v1/workspaces", json={"name": "No origin"}).status_code == 403
    headers, _ = owner
    assert client.post("/api/v1/workspaces", json={"name": "Bearer CLI"}, headers=headers).status_code == 201
    preflight = client.options(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_crud_search_filters_stage_notes_and_metrics(client, owner):
    headers, ws = owner
    stages = client.get(path(ws, "/stages"), headers=headers).json()
    assert [s["name"] for s in stages] == [
        "New Lead",
        "Contacted",
        "AI Qualifying",
        "Qualified",
        "Proposal",
        "Won",
        "Lost",
    ]
    data = {
        "name": "Olivia Chen",
        "company": "Northstar",
        "email": "olivia@example.com",
        "value": "12000.50",
        "source": "website",
    }
    created = client.post(path(ws, "/leads"), headers=headers, json=data)
    assert created.status_code == 201, created.text
    lead = created.json()
    assert lead["stage_id"] == stages[0]["id"]
    for query in ("?q=NORTHSTAR", "?source=website", "?status=new", "?stage_id=" + stages[0]["id"]):
        assert len(client.get(path(ws, "/leads" + query), headers=headers).json()["items"]) == 1
    assert not client.get(path(ws, "/leads?q=missing"), headers=headers).json()["items"]
    moved = client.post(
        path(ws, f"/leads/{lead['id']}/stage"), headers=headers, json={"stage_id": stages[3]["id"]}
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "new"  # Pipeline and qualification are separate concepts.
    update = {k: v for k, v in moved.json().items() if k not in ("id", "created_at", "updated_at")}
    update.update(status="qualified", summary="Ready to talk", company="Northstar Studio")
    assert client.patch(path(ws, "/leads/" + lead["id"]), headers=headers, json=update).status_code == 200
    assert (
        client.get(path(ws, "/leads/" + lead["id"]), headers=headers).json()["company"] == "Northstar Studio"
    )
    note_url = path(ws, f"/leads/{lead['id']}/notes")
    assert client.post(note_url, headers=headers, json={"body": "Discuss a pilot"}).status_code == 201
    assert client.get(note_url, headers=headers).json()[0]["body"] == "Discuss a pilot"
    metrics = client.get(path(ws, "/analytics/overview"), headers=headers).json()
    assert metrics["total_leads"] == metrics["qualified_leads"] == metrics["active_leads"] == 1
    assert metrics["qualification_rate"] == 100
    assert metrics["pipeline"][3]["count"] == 1
    assert metrics["pipeline"][3]["value"] == "12000.50"
    assert metrics["sources"] == [{"source": "website", "count": 1}]
    assert client.delete(path(ws, "/leads/" + lead["id"]), headers=headers).status_code == 204
    assert client.get(note_url, headers=headers).status_code == 404
    assert client.get(path(ws, "/analytics/overview"), headers=headers).json()["total_leads"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "Alex", "value": -1},
        {"name": "Alex", "email": "bad"},
        {"name": "Alex", "status": "invented"},
        {"name": "Alex", "workspace_id": str(uuid4())},
    ],
)
def test_invalid_lead(client, owner, payload):
    headers, ws = owner
    assert client.post(path(ws, "/leads"), headers=headers, json=payload).status_code == 422


def test_pagination(client, owner):
    headers, ws = owner
    ids = set()
    for n in range(5):
        ids.add(client.post(path(ws, "/leads"), headers=headers, json={"name": f"Lead {n}"}).json()["id"])
    seen = []
    cursor = ""
    while True:
        page = client.get(
            path(ws, "/leads?limit=2" + ("&cursor=" + cursor if cursor else "")), headers=headers
        ).json()
        seen.extend(lead["id"] for lead in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == len(set(seen)) == 5 and set(seen) == ids
    assert client.get(path(ws, "/leads?cursor=malformed"), headers=headers).status_code == 422


def test_cross_workspace_reads_writes_notes_settings_and_database_fk(client, owner):
    headers_a, ws_a = owner
    headers_b, ws_b = account(client, "other@example.com", workspace="Other business")
    lead = client.post(path(ws_a, "/leads"), headers=headers_a, json={"name": "Private A"}).json()
    stages_b = client.get(path(ws_b, "/stages"), headers=headers_b).json()
    for tail in (
        "/leads",
        "/stages",
        "/analytics/overview",
        "/business-profile",
        "/ai/settings",
        f"/leads/{lead['id']}",
        f"/leads/{lead['id']}/notes",
    ):
        assert client.get(path(ws_a, tail), headers=headers_b).status_code == 404
    assert client.post(path(ws_a, "/leads"), headers=headers_b, json={"name": "Intruder"}).status_code == 404
    assert client.delete(path(ws_a, f"/leads/{lead['id']}"), headers=headers_b).status_code == 404
    assert (
        client.post(
            path(ws_b, f"/leads/{lead['id']}/notes"), headers=headers_b, json={"body": "Intruder"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            path(ws_a, f"/leads/{lead['id']}/stage"), headers=headers_a, json={"stage_id": stages_b[0]["id"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            path(ws_a, "/leads"), headers=headers_a, json={"name": "Bad stage", "stage_id": stages_b[0]["id"]}
        ).status_code
        == 422
    )
    for method, tail, body in [
        ("put", "/ai/settings", {"provider": "gemini", "model": "gemini-2.5-flash"}),
        ("post", "/ai/test", {"provider": "gemini", "model": "gemini-2.5-flash"}),
        ("post", "/ai/generate", {"prompt": "Intruder"}),
    ]:
        assert getattr(client, method)(path(ws_a, tail), headers=headers_b, json=body).status_code == 404
    with SessionLocal() as db:
        row = db.get(Lead, lead["id"])
        row.stage_id = stages_b[0]["id"]
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_workspace_creation_and_business_profile(client, owner):
    headers, ws = owner
    assert client.get(path(ws, "/analytics/overview"), headers=headers).json()["qualification_rate"] == 0
    patch = {
        "name": "Acme Updated",
        "industry": "Technology",
        "website": "https://example.com",
        "description": "Builds useful things",
    }
    assert client.patch(path(ws, "/business-profile"), headers=headers, json=patch).status_code == 200
    assert client.get(path(ws, "/business-profile"), headers=headers).json()["industry"] == "Technology"
    second = client.post("/api/v1/workspaces", headers=headers, json={"name": "Second workspace"}).json()
    assert second["id"] != ws
    assert len(client.get("/api/v1/workspaces", headers=headers).json()) == 2
    assert len(client.get(path(second["id"], "/stages"), headers=headers).json()) == 7


def test_salesperson_cannot_manage_settings(client, owner):
    headers, ws = owner
    with SessionLocal() as db:
        membership = db.scalar(select(Membership).where(Membership.workspace_id == ws))
        membership.role = "salesperson"
        db.commit()
    assert client.get(path(ws, "/ai/settings"), headers=headers).json()["can_manage"] is False
    assert (
        client.put(
            path(ws, "/ai/settings"),
            headers=headers,
            json={"provider": "gemini", "model": "gemini-2.5-flash"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            path(ws, "/ai/test"), headers=headers, json={"provider": "gemini", "model": "gemini-2.5-flash"}
        ).status_code
        == 403
    )
    assert (
        client.patch(path(ws, "/business-profile"), headers=headers, json={"name": "Bad"}).status_code == 403
    )
    assert client.post(path(ws, "/leads"), headers=headers, json={"name": "Allowed"}).status_code == 201


def test_no_auth_and_health(client):
    assert client.get("/api/v1/health").json()["database"] == "connected"
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get(path(uuid4(), "/leads")).status_code == 401


def test_password_whitespace_is_preserved(client):
    password = "  password-with-spaces-123  "
    result = client.post(
        "/api/v1/auth/register",
        json={
            "email": "spaces@example.com",
            "password": password,
            "name": "Spaces",
            "workspace_name": "Spaces",
        },
    )
    assert result.status_code == 201
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "spaces@example.com", "password": password}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "spaces@example.com", "password": password.strip()}
        ).status_code
        == 401
    )


def test_request_size_is_bounded(client, owner):
    headers, ws = owner
    result = client.post(path(ws, "/leads"), headers=headers, json={"name": "x" * 70000})
    assert result.status_code == 413
