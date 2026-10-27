from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IntegrationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["website", "whatsapp", "meta_leads", "instagram"]
    credential_alias: str = Field(default="", max_length=100)
    ai_enabled: bool = False
    field_map: dict[str, str] = Field(default_factory=dict, max_length=10)

    @field_validator("field_map")
    @classmethod
    def mapping(cls, value):
        allowed = {
            "name",
            "email",
            "phone",
            "company",
            "message",
            "consent_to_contact",
            "external_contact_id",
        }
        if any(k not in allowed or not v or len(v) > 100 for k, v in value.items()):
            raise ValueError("Map canonical fields to top-level lead/form keys")
        return value


class IntegrationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool
    ai_enabled: bool


class WebsiteLead(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    name: str = Field(default="Website prospect", min_length=1, max_length=100)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=40)
    company: str = Field(default="", max_length=120)
    message: str = Field(default="", max_length=4000)
    external_contact_id: str = Field(default="", max_length=150)
    consent_to_contact: bool = False

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        if value:
            from email_validator import validate_email

            return validate_email(value, check_deliverability=False).normalized.casefold()
        return value

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, value):
        import re

        if not value:
            return value
        value = re.sub(r"[\s().-]", "", value)
        if not re.fullmatch(r"\+[1-9][0-9]{6,14}", value):
            raise ValueError("Phone must include country code")
        return value


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    external_contact_id: str = Field(min_length=1, max_length=200)
    contact: WebsiteLead
    text: str = Field(max_length=4000)
    occurred_at: datetime
    kind: Literal["message", "lead", "status", "leadgen"] = "message"
    metadata: dict = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timestamp must include timezone")
        return value


class ManualMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_.:-]{1,100}$")
    text: str = Field(min_length=1, max_length=4000)


class ThreadControl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["ai", "human"]
    reason: str = Field(min_length=3, max_length=300)
