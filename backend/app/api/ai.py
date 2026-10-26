from dataclasses import asdict
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.ai.catalogue import catalogue
from app.ai.providers import ProviderError, provider_for, validate_identifier
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import admin, limiter, member
from app.models.entities import ModelPreference
from app.schemas.contracts import Preference, Prompt

router = APIRouter(prefix="/workspaces/{ws}/ai", tags=["AI Models & Playground"])


@router.get("/settings")
def settings_get(ws: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    settings = get_settings()
    pref = db.get(ModelPreference, str(ws))
    return {
        "active": {"provider": pref.provider, "model": pref.model} if pref else None,
        "providers": [
            {
                "id": name,
                "name": title,
                "configured": bool(getattr(settings, f"{name}_api_key").get_secret_value()),
            }
            for name, title in [("gemini", "Google Gemini"), ("nvidia", "NVIDIA NIM")]
        ],
        "can_manage": membership.role == "admin",
    }


@router.get("/models")
async def models_get(
    ws: UUID, provider: Literal["gemini", "nvidia"], refresh: bool = False, membership=Depends(member)
):
    if refresh and membership.role != "admin":
        raise HTTPException(403, "Only workspace admins can refresh models")
    limiter.check(f"ai-models:{ws}", 20, 60)
    config = get_settings()
    result = await catalogue.get(config, provider, provider_for, refresh)
    return catalogue.decorate(result, ws, config)


@router.put("/settings", response_model=Preference)
async def settings_save(ws: UUID, body: Preference, membership=Depends(admin), db: Session = Depends(get_db)):
    await catalogue.validate(get_settings(), body.provider, body.model, provider_for)
    pref = db.get(ModelPreference, str(ws))
    if not pref:
        pref = ModelPreference(workspace_id=str(ws), **body.model_dump())
        db.add(pref)
    else:
        pref.provider, pref.model = body.provider, body.model
    db.commit()
    return body


async def execute(ws, config, provider, model, prompt=None):
    validate_identifier(model)
    try:
        adapter = provider_for(provider, config)
        result = (
            await adapter.generate(model, prompt)
            if prompt is not None
            else await adapter.check_connection(model)
        )
    except ProviderError as exc:
        catalogue.record(ws, config, provider, model, exc)
        raise
    catalogue.record(ws, config, provider, model)
    return asdict(result)


@router.post("/test")
async def connection_test(ws: UUID, body: Preference, membership=Depends(admin)):
    limiter.check(f"ai:{ws}", 10, 60)
    config = get_settings()
    # Fail missing credentials before discovery, without making any provider request.
    provider_for(body.provider, config).key(body.provider)
    await catalogue.validate(config, body.provider, body.model, provider_for)
    return await execute(ws, config, body.provider, body.model)


@router.post("/generate")
async def generate(ws: UUID, body: Prompt, membership=Depends(member), db: Session = Depends(get_db)):
    limiter.check(f"ai:{ws}", 10, 60)
    pref = db.get(ModelPreference, str(ws))
    if not pref:
        raise HTTPException(409, "Choose and save a default model in Settings → AI Models first")
    # A discovery outage must not prevent using an already-saved preference. The
    # generation endpoint remains authoritative about current model/account access.
    return await execute(ws, get_settings(), pref.provider, pref.model, body.prompt)
