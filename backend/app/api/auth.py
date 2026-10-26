from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import DUMMY_HASH, current_user, limiter, new_session, passwords, token_hash
from app.models.entities import AuthSession, Membership, User, Workspace
from app.schemas.contracts import Login, Register, UserOut, WorkspaceOut
from app.services.workspaces import create_workspace

router = APIRouter(prefix="/auth", tags=["Authentication"])


def issue(db, user, response):
    settings = get_settings()
    token = new_session(db, user, settings.session_ttl_seconds)
    db.commit()
    response.set_cookie(
        "easycrm_session",
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.session_ttl_seconds,
        path="/api",
    )
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": token, "token_type": "bearer", "user": UserOut.model_validate(user)}


@router.post("/register", status_code=201)
def register(body: Register, request: Request, response: Response, db: Session = Depends(get_db)):
    limiter.check(f"auth:{request.client.host}", 20, 300)
    user = User(name=body.name, email=str(body.email).lower(), password_hash=passwords.hash(body.password))
    try:
        db.add(user)
        db.flush()
        create_workspace(db, user.id, body.workspace_name)
        return issue(db, user, response)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Unable to register with this email")


@router.post("/login")
def login(body: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    limiter.check(f"auth:{request.client.host}", 20, 300)
    user = db.scalar(select(User).where(User.email == str(body.email).lower()))
    valid = passwords.verify(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Invalid email or password")
    return issue(db, user, response)


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    workspaces = db.scalars(
        select(Workspace).join(Membership).where(Membership.user_id == user.id).order_by(Workspace.created_at)
    ).all()
    return {
        "user": UserOut.model_validate(user),
        "workspaces": [WorkspaceOut.model_validate(w) for w in workspaces],
    }


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.cookies.get("easycrm_session", "")
    db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    db.commit()
    response.delete_cookie("easycrm_session", path="/api")
