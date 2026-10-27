"""Session 4 is additive and reversible on the suite's disposable PostgreSQL."""

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from app.core.database import engine


def test_channel_migration_preserves_session3_data(client, owner):
    headers, ws = owner
    lead = client.post(
        f"/api/v1/workspaces/{ws}/leads",
        headers=headers,
        json={"name": "Session 4 migration sentinel", "summary": "Preserve existing CRM", "value": "456.78"},
    ).json()
    config = Config("alembic.ini")
    try:
        command.downgrade(config, "57002a21df59")
        with engine.connect() as db:
            row = db.execute(
                text("SELECT name, summary, value FROM leads WHERE id=:id"), {"id": lead["id"]}
            ).one()
            assert tuple(map(str, row)) == ("Session 4 migration sentinel", "Preserve existing CRM", "456.78")
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        command.check(config)
    finally:
        command.upgrade(config, "head")
