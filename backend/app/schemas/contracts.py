from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

Status = Literal["new", "qualifying", "qualified", "needs-human", "disqualified", "closed"]
Source = Literal["manual", "website", "email", "referral", "whatsapp", "linkedin", "meta"]
Provider = Literal["gemini", "nvidia"]


class DTO(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid", str_strip_whitespace=True)


class Register(DTO):
    email: EmailStr
    password: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(min_length=10, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    workspace_name: str = Field(min_length=1, max_length=100)


class Login(DTO):
    email: EmailStr
    password: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(min_length=1, max_length=128)


class UserOut(DTO):
    id: str
    email: str
    name: str


class WorkspaceCreate(DTO):
    name: str = Field(min_length=1, max_length=100)


class WorkspacePatch(DTO):
    name: str = Field(min_length=1, max_length=100)
    industry: str = Field(default="", max_length=100)
    website: str = Field(default="", max_length=500, pattern=r"^(https?://[^\s]+)?$")
    description: str = Field(default="", max_length=5000)


class WorkspaceOut(DTO):
    id: str
    name: str
    industry: str
    website: str
    description: str


class StageOut(DTO):
    id: str
    name: str
    position: int
    color: str


class LeadFields(DTO):
    name: str = Field(min_length=1, max_length=100)
    company: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=254)
    phone: str = Field(default="", max_length=40)
    title: str = Field(default="", max_length=200)
    source: Source = "manual"
    status: Status = "new"
    value: Decimal = Field(default=Decimal(0), ge=0, le=999999999999, decimal_places=2)
    summary: str = Field(default="", max_length=1000)

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        if value:
            from pydantic import TypeAdapter

            return str(TypeAdapter(EmailStr).validate_python(value)).lower()
        return value


class LeadCreate(LeadFields):
    stage_id: UUID | None = None


class LeadUpdate(LeadFields):
    stage_id: UUID
    # Compatibility with clients that round-trip LeadOut; never used to set points.
    qualification_score: int | None = Field(default=None, ge=0, le=100)


class LeadOut(LeadFields):
    id: str
    qualification_score: int | None = None
    stage_id: str
    created_at: datetime
    updated_at: datetime


class StageChange(DTO):
    stage_id: UUID


class NoteCreate(DTO):
    body: str = Field(min_length=1, max_length=5000)


class NoteOut(DTO):
    id: str
    body: str
    author_id: str
    created_at: datetime


class Preference(DTO):
    provider: Provider
    model: str = Field(min_length=1, max_length=200)


class Prompt(DTO):
    prompt: str = Field(min_length=1, max_length=8000)
