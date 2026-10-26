from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.ai.providers import provider_for, validate_model
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
                "models": getattr(settings, f"{name}_models"),
            }
            for name, title in [("gemini", "Google Gemini"), ("nvidia", "NVIDIA NIM")]
        ],
        "can_manage": membership.role == "admin",
    }


@router.put("/settings", response_model=Preference)
def settings_save(ws: UUID, body: Preference, membership=Depends(admin), db: Session = Depends(get_db)):
    validate_model(get_settings(), body.provider, body.model)
    pref = db.get(ModelPreference, str(ws))
    if not pref:
        pref = ModelPreference(workspace_id=str(ws), **body.model_dump())
        db.add(pref)
    else:
        pref.provider, pref.model = body.provider, body.model
    db.commit()
    return body


@router.post("/test")
async def connection_test(ws: UUID, body: Preference, membership=Depends(admin)):
    limiter.check(f"ai:{ws}", 10, 60)
    config = get_settings()
    validate_model(config, body.provider, body.model)
    result = await provider_for(body.provider, config).check_connection(body.model)
    return asdict(result)


@router.post("/generate")
async def generate(ws: UUID, body: Prompt, membership=Depends(member), db: Session = Depends(get_db)):
    limiter.check(f"ai:{ws}", 10, 60)
    pref = db.get(ModelPreference, str(ws))
    if not pref:
        raise HTTPException(409, "Choose and save a default model in Settings → AI Models first")
    config = get_settings()
    validate_model(config, pref.provider, pref.model)
    return asdict(await provider_for(pref.provider, config).generate(pref.model, body.prompt))
