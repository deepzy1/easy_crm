import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import AuthSession, Membership, User, now

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
    """Single-process bounded sliding window. Use a shared gateway limiter before scaling out."""

    def __init__(self):
        self.events = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, bucket: str, limit: int, window: int):
        with self.lock:
            current = time.monotonic()
            # Expire all old buckets so arbitrary IP addresses cannot grow memory without bound.
            for key in list(self.events):
                while self.events[key] and self.events[key][0] < current:
                    self.events[key].popleft()
                if not self.events[key]:
                    del self.events[key]
            entries = self.events[bucket]
            if len(entries) >= limit:
                raise HTTPException(429, "Too many requests. Please try again later.")
            entries.append(current + window)


limiter = RateLimiter()
