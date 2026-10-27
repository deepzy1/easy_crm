from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Boolean,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(100))
    industry: Mapped[str] = mapped_column(String(100), default="")
    website: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Membership(Base):
    __tablename__ = "memberships"
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="admin")


class Stage(Base):
    __tablename__ = "pipeline_stages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(50))
    position: Mapped[int] = mapped_column(Integer)
    color: Mapped[str] = mapped_column(String(20))
    __table_args__ = (UniqueConstraint("workspace_id", "id"), UniqueConstraint("workspace_id", "position"))


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    stage_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(100))
    company: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(40), default="manual")
    status: Mapped[str] = mapped_column(String(30), default="new")
    value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    summary: Mapped[str] = mapped_column(String(1000), default="")
    qualification_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "stage_id"], ["pipeline_stages.workspace_id", "pipeline_stages.id"]
        ),
        UniqueConstraint("workspace_id", "id"),
        Index("ix_leads_workspace_created", "workspace_id", "created_at", "id"),
        Index("ix_leads_workspace_status", "workspace_id", "status"),
    )


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String(36))
    lead_id: Mapped[str] = mapped_column(String(36))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "lead_id"], ["leads.workspace_id", "leads.id"], ondelete="CASCADE"
        ),
    )


class ProviderConfig(Base):
    __tablename__ = "ai_provider_configurations"
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    # Credentials are deployment configuration, never persisted here.


class ModelPreference(Base):
    __tablename__ = "ai_model_preferences"
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "provider"],
            ["ai_provider_configurations.workspace_id", "ai_provider_configurations.provider"],
        ),
    )


class QualificationTemplate(Base):
    __tablename__ = "qualification_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    rules: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("workspace_id", "version"),
        UniqueConstraint("workspace_id", "id"),
    )


class KnowledgeText(Base):
    """Reviewed text only; no remote fetches or uploads in Session 3."""

    __tablename__ = "qualification_knowledge"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    text: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class QualificationConversation(Base):
    __tablename__ = "qualification_conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String(36))
    lead_id: Mapped[str] = mapped_column(String(36))
    template_id: Mapped[str] = mapped_column(String(36))
    channel: Mapped[str] = mapped_column(String(30))
    state: Mapped[str] = mapped_column(String(30), default="new")
    mode: Mapped[str] = mapped_column(String(10), default="ai")
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    assessment: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "lead_id"], ["leads.workspace_id", "leads.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "template_id"],
            ["qualification_templates.workspace_id", "qualification_templates.id"],
        ),
        UniqueConstraint("workspace_id", "lead_id", "channel"),
        UniqueConstraint("workspace_id", "id"),
    )


class QualificationEvent(Base):
    """Immutable receipt, extraction/assessment snapshot, or human control audit."""

    __tablename__ = "qualification_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String(36))
    conversation_id: Mapped[str] = mapped_column(String(36))
    channel: Mapped[str] = mapped_column(String(30))
    external_message_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["qualification_conversations.workspace_id", "qualification_conversations.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("workspace_id", "channel", "external_message_id"),
        Index("ix_qualification_events_timeline", "workspace_id", "conversation_id", "created_at", "id"),
    )


class Integration(Base):
    __tablename__ = "integrations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(30))
    credential_alias: Mapped[str] = mapped_column(String(100), default="")
    external_account_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    field_map: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("workspace_id", "id"),
        UniqueConstraint("kind", "external_account_id"),
    )


class ChannelContact(Base):
    __tablename__ = "channel_contacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String(36))
    lead_id: Mapped[str] = mapped_column(String(36))
    identity: Mapped[str] = mapped_column(String(320))
    consent_to_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "lead_id"], ["leads.workspace_id", "leads.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("workspace_id", "identity"),
        UniqueConstraint("workspace_id", "id"),
    )


class ChannelThread(Base):
    __tablename__ = "channel_threads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String(36))
    integration_id: Mapped[str] = mapped_column(String(36))
    contact_id: Mapped[str] = mapped_column(String(36))
    external_contact_id: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(10), default="human")
    control_version: Mapped[int] = mapped_column(Integer, default=0)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "integration_id"],
            ["integrations.workspace_id", "integrations.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "contact_id"],
            ["channel_contacts.workspace_id", "channel_contacts.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("workspace_id", "integration_id", "external_contact_id"),
        UniqueConstraint("workspace_id", "id"),
    )


class InboundEvent(Base):
    __tablename__ = "channel_inbound_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String(36))
    integration_id: Mapped[str] = mapped_column(String(36))
    external_event_id: Mapped[str] = mapped_column(String(200))
    payload_hash: Mapped[str] = mapped_column(String(64))
    # Minimized normalized envelope, never the raw Meta/form request.
    envelope: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(300), default="")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "integration_id"],
            ["integrations.workspace_id", "integrations.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("integration_id", "external_event_id"),
        Index("ix_channel_inbound_due", "status", "available_at"),
    )


class ChannelMessage(Base):
    __tablename__ = "channel_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String(36))
    thread_id: Mapped[str] = mapped_column(String(36))
    dedupe_key: Mapped[str] = mapped_column(String(200))
    external_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    direction: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    control_version: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(300), default="")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "thread_id"],
            ["channel_threads.workspace_id", "channel_threads.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("workspace_id", "dedupe_key"),
        Index("ix_channel_outbox_due", "status", "available_at"),
    )


class WebhookLog(Base):
    __tablename__ = "channel_webhook_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = mapped_column(String(36))
    integration_id: Mapped[str] = mapped_column(String(36))
    result: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "integration_id"],
            ["integrations.workspace_id", "integrations.id"],
            ondelete="CASCADE",
        ),
    )
