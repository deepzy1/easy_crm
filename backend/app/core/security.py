import hashlib
import secrets
import time
from datetime import timedelta
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.models.entities import AuthSession, Membership, RateLimitBucket, User, now
from sqlalchemy.dialects.postgresql import insert

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("dummy-password-for-timing")


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(db, user, ttl):
    token = secrets.token_urlsafe(48)
    db.add(
        AuthSession(token_hash=token_hash(token), user_id=user.id, expires_at=now() + timedelta(seconds=ttl))
    )
    return token


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else request.cookies.get("easycrm_session", "")
    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_hash(token), AuthSession.expires_at > now())
    )
    if not session:
        raise HTTPException(401, "Sign in to continue")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Sign in to continue")
    return user


def member(ws: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Membership:
    membership = db.get(Membership, (str(ws), user.id))
    if not membership:
        raise HTTPException(404, "Workspace not found")
    return membership


def admin(membership: Membership = Depends(member)) -> Membership:
    if membership.role != "admin":
        raise HTTPException(403, "Workspace administrator access required")
    return membership


class RateLimiter:
    """Atomic fixed-window counters shared by API and worker processes via PostgreSQL."""

    def check(self, bucket: str, limit: int, window: int):
        current = int(time.time())
        start = current - current % window
        # Hash identifiers: auth buckets otherwise contain a client IP address.
        key = hashlib.sha256(f"{window}:{bucket}".encode()).hexdigest()
        with SessionLocal() as db:
            statement = insert(RateLimitBucket).values(
                key=key, window_start=start, count=1, expires_at=now() + timedelta(seconds=window)
            )
            count = db.scalar(
                statement.on_conflict_do_update(
                    index_elements=[RateLimitBucket.key, RateLimitBucket.window_start],
                    set_={"count": RateLimitBucket.count + 1},
                ).returning(RateLimitBucket.count)
            )
            db.commit()
        if count > limit:
            raise HTTPException(429, "Too many requests. Please try again later.")


limiter = RateLimiter()
