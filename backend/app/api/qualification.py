from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.crm import scoped_lead
from app.core.database import get_db
from app.core.security import admin, member
from app.models.entities import (
    KnowledgeText,
    QualificationConversation,
    QualificationEvent,
    QualificationTemplate,
    Workspace,
)
from app.schemas.qualification import ActionPlan, Control, Incoming, KnowledgeInput, TemplateInput
from app.services.qualification import control_conversation, examples, process_incoming_message, save_template

router = APIRouter(prefix="/workspaces/{ws}", tags=["Qualification"])


@router.get("/qualification/templates")
def templates(ws: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(QualificationTemplate)
        .where(QualificationTemplate.workspace_id == str(ws))
        .order_by(QualificationTemplate.version.desc())
    ).all()
    return {"items": rows, "examples": examples(), "can_manage": membership.role == "admin"}


@router.post("/qualification/templates", status_code=201)
def template_create(ws: UUID, body: TemplateInput, membership=Depends(admin), db: Session = Depends(get_db)):
    row = save_template(db, ws, body)
    db.commit()
    return row


@router.post("/qualification/templates/{template_id}/activate")
def template_activate(ws: UUID, template_id: UUID, membership=Depends(admin), db: Session = Depends(get_db)):
    db.scalar(select(Workspace).where(Workspace.id == str(ws)).with_for_update())
    row = db.scalar(
        select(QualificationTemplate).where(
            QualificationTemplate.workspace_id == str(ws), QualificationTemplate.id == str(template_id)
        )
    )
    if not row:
        raise HTTPException(404, "Template not found")
    for template in db.scalars(
        select(QualificationTemplate).where(QualificationTemplate.workspace_id == str(ws))
    ):
        template.active = template.id == row.id
    db.commit()
    return row


@router.get("/qualification/knowledge")
def knowledge(ws: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    return db.scalars(
        select(KnowledgeText)
        .where(KnowledgeText.workspace_id == str(ws))
        .order_by(KnowledgeText.created_at.desc())
        .limit(100)
    ).all()


@router.post("/qualification/knowledge", status_code=201)
def knowledge_create(
    ws: UUID, body: KnowledgeInput, membership=Depends(admin), db: Session = Depends(get_db)
):
    row = KnowledgeText(workspace_id=str(ws), **body.model_dump())
    db.add(row)
    db.commit()
    return row


@router.delete("/qualification/knowledge/{source_id}", status_code=204)
def knowledge_delete(ws: UUID, source_id: UUID, membership=Depends(admin), db: Session = Depends(get_db)):
    row = db.scalar(
        select(KnowledgeText).where(KnowledgeText.workspace_id == str(ws), KnowledgeText.id == str(source_id))
    )
    if not row:
        raise HTTPException(404, "Source not found")
    db.delete(row)
    db.commit()


@router.post("/qualification/simulate", response_model=ActionPlan)
async def simulate(ws: UUID, body: Incoming, membership=Depends(member), db: Session = Depends(get_db)):
    try:
        result = await process_incoming_message(
            db,
            str(ws),
            str(body.lead_id),
            "simulator",
            body.external_message_id,
            body.text,
            body.timestamp,
            membership.user_id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Concurrent message receipt. Retry with the same external message ID."
        ) from None
    return result


@router.get("/leads/{lead_id}/qualification")
def qualification_get(ws: UUID, lead_id: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    scoped_lead(db, ws, lead_id)
    conversation = db.scalar(
        select(QualificationConversation).where(
            QualificationConversation.workspace_id == str(ws),
            QualificationConversation.lead_id == str(lead_id),
        )
    )
    if not conversation:
        return {"conversation": None, "events": []}
    events = db.scalars(
        select(QualificationEvent)
        .where(
            QualificationEvent.workspace_id == str(ws), QualificationEvent.conversation_id == conversation.id
        )
        .order_by(QualificationEvent.created_at, QualificationEvent.id)
    ).all()
    return {"conversation": conversation, "events": events}


@router.post("/leads/{lead_id}/qualification/control")
def control(
    ws: UUID, lead_id: UUID, body: Control, membership=Depends(member), db: Session = Depends(get_db)
):
    result = control_conversation(db, ws, lead_id, body, membership.user_id)
    db.commit()
    return result
