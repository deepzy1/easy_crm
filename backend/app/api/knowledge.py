from uuid import UUID
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import admin, limiter, member
from app.models.entities import KnowledgeText
from app.schemas.contracts import DTO
from app.services import knowledge
from app.services.qualification import retrieve_knowledge

router = APIRouter(prefix="/workspaces/{ws}/knowledge", tags=["Knowledge"])


class WebsiteInput(DTO):
    title: str = Field(min_length=1, max_length=150)
    url: str = Field(min_length=1, max_length=500)
    authorized: bool

    @field_validator("url")
    @classmethod
    def credential_free_url(cls, value):
        try:
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
                or parsed.port not in (None, 443)
            ):
                raise ValueError
        except ValueError:
            raise ValueError(
                "Use a public HTTPS URL without credentials, query parameters or fragments"
            ) from None
        return value


class ReviewInput(DTO):
    title: str = Field(min_length=1, max_length=150)
    text: str = Field(min_length=1, max_length=12000)
    approved: bool


def source_get(db, ws, source_id):
    row = db.scalar(
        select(KnowledgeText).where(KnowledgeText.workspace_id == str(ws), KnowledgeText.id == str(source_id))
    )
    if not row:
        raise HTTPException(404, "Source not found")
    return row


def store(db, ws, title, kind, origin, extract):
    limiter.check(f"ingest:{ws}", 10, 60)
    row = KnowledgeText(
        workspace_id=str(ws),
        title=title,
        kind=kind,
        origin=origin,
        text="",
        state="processing",
        approved=False,
    )
    db.add(row)
    db.commit()
    try:
        row.text, row.state = extract(), "ready"
    except knowledge.IngestionError as exc:
        row.state, row.error = "failed", str(exc)
    db.commit()
    return row


@router.get("/sources")
def sources(ws: UUID, membership=Depends(member), db: Session = Depends(get_db)):
    return {
        "items": db.scalars(
            select(KnowledgeText)
            .where(KnowledgeText.workspace_id == str(ws))
            .order_by(KnowledgeText.created_at.desc())
            .limit(100)
        ).all(),
        "can_manage": membership.role == "admin",
    }


@router.post("/sources", status_code=201)
def website(ws: UUID, body: WebsiteInput, membership=Depends(admin), db: Session = Depends(get_db)):
    if not body.authorized:
        raise HTTPException(422, "Confirm you are authorized to ingest this public page")
    return store(db, ws, body.title, "website", body.url, lambda: knowledge.fetch_page(body.url))


@router.post("/uploads", status_code=201)
async def upload(
    ws: UUID,
    request: Request,
    title: str = Query(min_length=1, max_length=150),
    membership=Depends(admin),
    db: Session = Depends(get_db),
):
    if request.headers.get("content-type", "").split(";")[0] != "application/pdf":
        raise HTTPException(415, "Send PDF bytes with Content-Type: application/pdf")
    raw = await request.body()
    # Extraction is bounded blocking work; keep it off the ASGI event loop.
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(
        store, db, ws, title, "pdf", "Uploaded PDF (first 30 pages)", lambda: knowledge.extract_pdf(raw)
    )


@router.patch("/sources/{source_id}")
def review(
    ws: UUID, source_id: UUID, body: ReviewInput, membership=Depends(admin), db: Session = Depends(get_db)
):
    row = source_get(db, ws, source_id)
    if row.state != "ready":
        raise HTTPException(
            409, "Only successfully extracted sources can be reviewed; remove failed sources and ingest again"
        )
    row.title, row.text, row.approved = body.title, body.text, body.approved
    db.commit()
    return row


@router.delete("/sources/{source_id}", status_code=204)
def remove(ws: UUID, source_id: UUID, membership=Depends(admin), db: Session = Depends(get_db)):
    db.delete(source_get(db, ws, source_id))
    db.commit()


@router.get("/search")
def search(
    ws: UUID,
    q: str = Query(min_length=1, max_length=500),
    membership=Depends(member),
    db: Session = Depends(get_db),
):
    return {"items": retrieve_knowledge(db, ws, q)}
