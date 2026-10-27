from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator
from app.schemas.contracts import DTO

State = Literal["new", "qualifying", "qualified", "needs_human", "disqualified", "closed"]


class Criterion(DTO):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    question: str = Field(min_length=1, max_length=250)
    kind: Literal["text", "number"] = "text"
    required: bool = True
    weight: int = Field(ge=0, le=100)
    operator: Literal["present", "one_of", "minimum"] = "present"
    choices: list[str] = Field(default_factory=list, max_length=30)
    minimum: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    disqualify_on_mismatch: bool = False
    handoff_on_match: bool = False

    @model_validator(mode="after")
    def rule_valid(self):
        if self.operator == "one_of" and (
            self.kind != "text"
            or not self.choices
            or any(not x.strip() or len(x) > 150 for x in self.choices)
        ):
            raise ValueError("one_of requires text choices")
        if self.operator == "minimum" and (self.kind != "number" or self.minimum is None):
            raise ValueError("minimum requires a numeric minimum")
        return self


class TemplateInput(DTO):
    name: str = Field(min_length=1, max_length=100)
    criteria: list[Criterion] = Field(min_length=1, max_length=15)
    qualified_threshold: int = Field(default=75, ge=1, le=100)
    review_threshold: int = Field(default=40, ge=0, le=99)
    confidence_threshold: float = Field(default=0.8, ge=0.5, le=1)
    handoff_when_qualified: bool = True
    activate: bool = True

    @model_validator(mode="after")
    def rules_valid(self):
        if sum(c.weight for c in self.criteria) != 100:
            raise ValueError("Weights must total exactly 100")
        if len({c.key for c in self.criteria}) != len(self.criteria):
            raise ValueError("Field keys must be unique")
        if self.review_threshold >= self.qualified_threshold:
            raise ValueError("Review threshold must be below qualified threshold")
        return self


class KnowledgeInput(DTO):
    title: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=1, max_length=12000)
    approved: bool = False


class Candidate(DTO):
    key: str = Field(max_length=40)
    value: StrictStr | StrictInt | StrictFloat | None
    evidence: str = Field(default="", max_length=500)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    correction: StrictBool = False


class Quote(DTO):
    source_id: str = Field(max_length=36)
    quote: str = Field(min_length=1, max_length=1000)


class Extraction(DTO):
    fields: list[Candidate] = Field(default_factory=list, max_length=15)
    quotes: list[Quote] = Field(default_factory=list, max_length=3)
    needs_human: StrictBool = False


class Incoming(DTO):
    lead_id: UUID
    external_message_id: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=1, max_length=4000)
    timestamp: datetime

    @model_validator(mode="after")
    def aware(self):
        if self.timestamp.tzinfo is None:
            raise ValueError("Timestamp must include timezone")
        return self


class Control(DTO):
    action: Literal["takeover", "resume", "close", "override"]
    reason: str = Field(min_length=1, max_length=500)
    state: State | None = None

    @model_validator(mode="after")
    def override_state(self):
        if (self.action == "override") != (self.state is not None):
            raise ValueError("Only override requires a state")
        return self


class ActionPlan(DTO):
    conversation_id: str
    lead_id: str
    state: State
    mode: Literal["ai", "human"]
    reply: str | None
    dispatch: Literal["none"] = "none"
    assessment: dict
    fields: dict
    citations: list[dict]
    model: dict | None
    duplicate: bool = False
