import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.invite import Invite

TOKEN_NBYTES = 32
INVITE_TTL = timedelta(days=7)
PASSWORD_RESET_TTL = timedelta(hours=2)


def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_NBYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_invite_by_token(db: Session, token: str) -> Invite | None:
    return db.query(Invite).filter(Invite.token_hash == hash_token(token)).first()
