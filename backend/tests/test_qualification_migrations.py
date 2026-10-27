"""Reversible additive migration on the explicitly disposable suite database."""

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from app.core.database import engine


def test_session3_migration_preserves_existing_lead_and_reapplies(client, owner):
    headers, ws = owner
    lead = client.post(
        f"/api/v1/workspaces/{ws}/leads",
        headers=headers,
        json={"name": "Migration sentinel", "summary": "Preserve this real row", "value": "123.45"},
    ).json()
    config = Config("alembic.ini")
    try:
        command.downgrade(config, "be78ada7931e")
        with engine.connect() as connection:
            saved = connection.execute(
                text("SELECT name, summary, value FROM leads WHERE id=:id"), {"id": lead["id"]}
            ).one()
            assert tuple(map(str, saved)) == ("Migration sentinel", "Preserve this real row", "123.45")
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        command.check(config)
        saved = client.get(f"/api/v1/workspaces/{ws}/leads/{lead['id']}", headers=headers).json()
        assert saved["name"] == lead["name"] and saved["qualification_score"] is None
    finally:
        command.upgrade(config, "head")
