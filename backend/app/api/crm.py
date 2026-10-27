import base64
import json
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.core.database import get_db
from app.core.security import admin, current_user, member
from app.models.entities import Lead, Membership, Note, Stage, User, Workspace, QualificationConversation
from app.schemas.contracts import (
    LeadCreate,
    LeadOut,
    LeadUpdate,
    NoteCreate,
    NoteOut,
    Source,
    StageChange,
    StageOut,
    Status,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspacePatch,
)
from app.services.workspaces import create_workspace

router = APIRouter(tags=["Workspaces & CRM"])


def scoped_lead(db, ws, lead_id, lock=False):
    query = select(Lead).where(Lead.id == str(lead_id), Lead.workspace_id == str(ws))
    try:
        lead = db.scalar(query.with_for_update(nowait=True) if lock else query)
    except OperationalError:
        raise HTTPException(409, "This lead is being processed. Retry manually shortly.") from None
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


def scoped_stage(db, ws, stage_id):
    stage = db.scalar(select(Stage).where(Stage.id == str(stage_id), Stage.workspace_id == str(ws)))
    if not stage:
        raise HTTPException(422, "Stage is not in this workspace")
    return stage


@router.get("/workspaces", response_model=list[WorkspaceOut])
def workspaces(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(
        select(Workspace).join(Membership).where(Membership.user_id == user.id).order_by(Workspace.created_at)
    ).all()


@router.post("/workspaces", status_code=201, response_model=WorkspaceOut)
def workspace_create(
    body: WorkspaceCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    workspace = create_workspace(db, user.id, body.name)
    db.commit()
    return workspace


@router.get("/workspaces/{ws}/business-profile", response_model=WorkspaceOut)
def business_profile(ws: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    return db.get(Workspace, str(ws))


@router.patch("/workspaces/{ws}/business-profile", response_model=WorkspaceOut)
def business_update(ws: UUID, body: WorkspacePatch, membership=Depends(admin), db: Session = Depends(get_db)):
    workspace = db.get(Workspace, str(ws))
    for key, value in body.model_dump().items():
        setattr(workspace, key, value)
    db.commit()
    return workspace


@router.get("/workspaces/{ws}/stages", response_model=list[StageOut])
def stages(ws: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    return db.scalars(select(Stage).where(Stage.workspace_id == str(ws)).order_by(Stage.position)).all()


@router.get("/workspaces/{ws}/leads")
def leads(
    ws: UUID,
    q: str = Query("", max_length=200),
    stage_id: UUID | None = None,
    status: Status | None = None,
    source: Source | None = None,
    cursor: str | None = Query(None, max_length=300),
    limit: int = Query(50, ge=1, le=200),
    membership=Depends(member),
    db: Session = Depends(get_db),
):
    query = select(Lead).where(Lead.workspace_id == str(ws))
    if q:
        search = f"%{q}%"
        query = query.where(
            or_(
                Lead.name.ilike(search),
                Lead.company.ilike(search),
                Lead.email.ilike(search),
                Lead.title.ilike(search),
            )
        )
    if stage_id:
        query = query.where(Lead.stage_id == str(stage_id))
    if status:
        query = query.where(Lead.status == status)
    if source:
        query = query.where(Lead.source == source)
    if cursor:
        try:
            date, identity = json.loads(base64.urlsafe_b64decode(cursor).decode())
            date = datetime.fromisoformat(date)
            UUID(identity)
        except (ValueError, TypeError, json.JSONDecodeError):
            raise HTTPException(422, "Invalid pagination cursor")
        query = query.where(or_(Lead.created_at < date, and_(Lead.created_at == date, Lead.id < identity)))
    rows = db.scalars(query.order_by(Lead.created_at.desc(), Lead.id.desc()).limit(limit + 1)).all()
    items = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        next_cursor = base64.urlsafe_b64encode(
            json.dumps([items[-1].created_at.isoformat(), items[-1].id]).encode()
        ).decode()
    return {"items": [LeadOut.model_validate(row) for row in items], "next_cursor": next_cursor}


@router.post("/workspaces/{ws}/leads", status_code=201, response_model=LeadOut)
def lead_create(ws: UUID, body: LeadCreate, membership=Depends(member), db: Session = Depends(get_db)):
    stage_id = body.stage_id
    if stage_id is None:
        stage_id = db.scalar(select(Stage.id).where(Stage.workspace_id == str(ws), Stage.position == 0))
    scoped_stage(db, ws, stage_id)
    lead = Lead(workspace_id=str(ws), **body.model_dump(exclude={"stage_id"}), stage_id=str(stage_id))
    db.add(lead)
    db.commit()
    return lead


@router.get("/workspaces/{ws}/leads/{lead_id}", response_model=LeadOut)
def lead_get(ws: UUID, lead_id: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    return scoped_lead(db, ws, lead_id)


@router.patch("/workspaces/{ws}/leads/{lead_id}", response_model=LeadOut)
def lead_update(
    ws: UUID, lead_id: UUID, body: LeadUpdate, membership=Depends(member), db: Session = Depends(get_db)
):
    lead = scoped_lead(db, ws, lead_id, lock=True)
    scoped_stage(db, ws, body.stage_id)
    if body.qualification_score is not None and body.qualification_score != lead.qualification_score:
        raise HTTPException(422, "Qualification points are computed from rules and cannot be edited")
    conversation = db.scalar(
        select(QualificationConversation).where(
            QualificationConversation.workspace_id == str(ws),
            QualificationConversation.lead_id == str(lead_id),
        )
    )
    if conversation and body.status != lead.status:
        raise HTTPException(409, "Use qualification human override to change this lead's decision")
    for key, value in body.model_dump(exclude={"qualification_score"}).items():
        setattr(lead, key, str(value) if key == "stage_id" else value)
    db.commit()
    return lead


@router.post("/workspaces/{ws}/leads/{lead_id}/stage", response_model=LeadOut)
def lead_stage(
    ws: UUID, lead_id: UUID, body: StageChange, membership=Depends(member), db: Session = Depends(get_db)
):
    lead = scoped_lead(db, ws, lead_id)
    scoped_stage(db, ws, body.stage_id)
    lead.stage_id = str(body.stage_id)
    db.commit()
    return lead


@router.delete("/workspaces/{ws}/leads/{lead_id}", status_code=204)
def lead_delete(ws: UUID, lead_id: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    db.delete(scoped_lead(db, ws, lead_id))
    db.commit()


@router.get("/workspaces/{ws}/leads/{lead_id}/notes", response_model=list[NoteOut])
def notes(ws: UUID, lead_id: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    scoped_lead(db, ws, lead_id)
    return db.scalars(
        select(Note)
        .where(Note.workspace_id == str(ws), Note.lead_id == str(lead_id))
        .order_by(Note.created_at)
    ).all()


@router.post("/workspaces/{ws}/leads/{lead_id}/notes", status_code=201, response_model=NoteOut)
def note_create(
    ws: UUID,
    lead_id: UUID,
    body: NoteCreate,
    membership=Depends(member),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    scoped_lead(db, ws, lead_id)
    note = Note(workspace_id=str(ws), lead_id=str(lead_id), author_id=user.id, body=body.body)
    db.add(note)
    db.commit()
    return note


@router.get("/workspaces/{ws}/analytics/overview")
def overview(ws: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(Lead).where(Lead.workspace_id == str(ws))) or 0
    qualified = (
        db.scalar(
            select(func.count())
            .select_from(Lead)
            .where(Lead.workspace_id == str(ws), Lead.status == "qualified")
        )
        or 0
    )
    active = (
        db.scalar(
            select(func.count())
            .select_from(Lead)
            .where(Lead.workspace_id == str(ws), Lead.status.not_in(["closed", "disqualified"]))
        )
        or 0
    )
    source_rows = db.execute(
        select(Lead.source, func.count())
        .where(Lead.workspace_id == str(ws))
        .group_by(Lead.source)
        .order_by(func.count().desc())
    ).all()
    stage_rows = db.execute(
        select(Stage.id, Stage.name, Stage.color, func.count(Lead.id), func.coalesce(func.sum(Lead.value), 0))
        .outerjoin(Lead, and_(Lead.stage_id == Stage.id, Lead.workspace_id == str(ws)))
        .where(Stage.workspace_id == str(ws))
        .group_by(Stage.id)
        .order_by(Stage.position)
    ).all()
    recent = db.scalars(
        select(Lead)
        .where(Lead.workspace_id == str(ws))
        .order_by(Lead.created_at.desc(), Lead.id.desc())
        .limit(5)
    ).all()
    return {
        "total_leads": total,
        "qualified_leads": qualified,
        "active_leads": active,
        "qualification_rate": round(qualified / total * 100, 1) if total else 0,
        "sources": [{"source": row[0], "count": row[1]} for row in source_rows],
        "pipeline": [
            {"id": row[0], "name": row[1], "color": row[2], "count": row[3], "value": str(row[4])}
            for row in stage_rows
        ],
        "recent_leads": [LeadOut.model_validate(row) for row in recent],
    }
