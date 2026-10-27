import os

import pytest

TEST_URL = os.getenv("TEST_DATABASE_URL", "")
if not TEST_URL or not TEST_URL.split("?")[0].endswith("_test"):
    raise pytest.UsageError("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test.")
os.environ["DATABASE_URL"] = TEST_URL
os.environ["GEMINI_API_KEY"] = ""
os.environ["NVIDIA_API_KEY"] = ""

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    command.upgrade(Config("alembic.ini"), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(migrated_database):
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(delete(table))
        db.commit()
    from app.ai.catalogue import catalogue

    catalogue.clear()


@pytest.fixture
def client():
    with TestClient(app, headers={"Origin": "http://localhost:5173"}) as client:
        yield client


def account(client, email="alex@example.com", name="Alex Morgan", workspace="Acme Studio"):
    result = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Test-password-123!", "name": name, "workspace_name": workspace},
    )
    assert result.status_code == 201, result.text
    headers = {"Authorization": "Bearer " + result.json()["access_token"]}
    me = client.get("/api/v1/auth/me", headers=headers).json()
    return headers, me["workspaces"][0]["id"]


@pytest.fixture
def owner(client):
    return account(client)
