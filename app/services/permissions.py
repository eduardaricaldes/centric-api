from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.event import Event
from app.models.ministry_member import MinistryMember
from app.models.playlist import Playlist
from app.models.roles import MinistryRole, UserRole
from app.models.user import User


def ensure_ministry_manager(db: Session, user: User, ministry_id: int) -> None:
    if user.role == UserRole.ADMIN:
        return

    membership = (
        db.query(MinistryMember)
        .filter(
            MinistryMember.ministry_id == ministry_id,
            MinistryMember.user_id == user.id,
            MinistryMember.role == MinistryRole.LEADER,
        )
        .first()
    )
    if user.role != UserRole.LEADER or membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ministry leader access required",
        )


def ensure_event_owner(db: Session, user: User, event: Event) -> None:
    if user.role == UserRole.ADMIN:
        return

    if user.role != UserRole.LEADER or event.created_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Event manager access required",
        )


def ensure_event_collaborator(db: Session, user: User, event: Event) -> None:
    if user.role in {UserRole.ADMIN, UserRole.LEADER}:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Event manager access required",
    )


def ensure_playlist_manager(db: Session, user: User, playlist: Playlist) -> None:
    if user.role == UserRole.ADMIN:
        return

    if user.role == UserRole.LEADER and playlist.created_by == user.id:
        return

    if playlist.event_id is not None:
        event = db.query(Event).filter(Event.id == playlist.event_id).first()
        if event is not None:
            ensure_event_collaborator(db, user, event)
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Playlist manager access required",
    )
