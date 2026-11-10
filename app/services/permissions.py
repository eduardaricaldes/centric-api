from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment import Assignment
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


def ensure_password_reset_allowed(db: Session, user: User, target: User) -> None:
    """ADMIN redefine a senha de qualquer um; LEADER, só de MEMBER do ministério que lidera.

    O link de redefinição dá acesso à conta do alvo, então quem gera nunca pode
    alcançar uma conta com mais poder que a sua.
    """
    if user.role == UserRole.ADMIN:
        return

    led_ministries = (
        db.query(MinistryMember.ministry_id)
        .filter(
            MinistryMember.user_id == user.id,
            MinistryMember.role == MinistryRole.LEADER,
        )
        .subquery()
    )
    shares_ministry = (
        db.query(MinistryMember)
        .filter(
            MinistryMember.user_id == target.id,
            MinistryMember.ministry_id.in_(select(led_ministries)),
        )
        .first()
        is not None
    )
    if user.role != UserRole.LEADER or target.role != UserRole.MEMBER or not shares_ministry:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
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


def ensure_share_link_manager(
    db: Session,
    user: User,
    *,
    event: Event | None = None,
) -> None:
    """ADMIN compartilha qualquer coisa; LEADER, só eventos dos ministérios que lidera.

    O evento é "do ministério" quando foi criado pelo líder ou quando alguém de
    um ministério que ele lidera está escalado nele. Música avulsa é só do ADMIN.
    """
    if user.role == UserRole.ADMIN:
        return

    if user.role == UserRole.LEADER and event is not None:
        if event.created_by == user.id:
            return

        led_ministries = (
            db.query(MinistryMember.ministry_id)
            .filter(
                MinistryMember.user_id == user.id,
                MinistryMember.role == MinistryRole.LEADER,
            )
            .subquery()
        )
        serves_led_ministry = (
            db.query(Assignment.id)
            .filter(
                Assignment.event_id == event.id,
                Assignment.ministry_id.in_(select(led_ministries)),
            )
            .first()
            is not None
        )
        if serves_led_ministry:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Share link manager access required",
    )
