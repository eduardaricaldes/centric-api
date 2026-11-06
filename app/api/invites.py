from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.invite import Invite, InviteKind
from app.models.ministry import Ministry
from app.models.roles import MinistryRole, UserRole
from app.models.user import User
from app.schemas.invite import (
    InviteCreate,
    InviteCreateResponse,
    InviteListResponse,
)
from app.services.auth_services import get_user_by_email
from app.services.invites import INVITE_TTL, generate_token, hash_token, utcnow
from app.services.permissions import ensure_ministry_manager

invites_router = APIRouter(prefix="/invites", tags=["Invites"])


def serialize_invite(invite: Invite) -> dict:
    return {
        "id": invite.id,
        "email": invite.email,
        "role": invite.role,
        "ministry_id": invite.ministry_id,
        "ministry_name": invite.ministry.name if invite.ministry else None,
        "ministry_role": invite.ministry_role,
        "instrument": invite.instrument,
        "created_by": invite.created_by,
        "created_by_name": invite.creator.name,
        "expires_at": invite.expires_at,
        "created_at": invite.created_at,
    }


@invites_router.post(
    "/",
    response_model=InviteCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invite(
    payload: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {UserRole.ADMIN, UserRole.LEADER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN or LEADER can create invites",
        )

    if current_user.role == UserRole.LEADER:
        if payload.role != UserRole.MEMBER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Leaders can only invite MEMBER",
            )
        if payload.ministry_role != MinistryRole.MEMBER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only ADMIN can set a member as LEADER",
            )
        if payload.ministry_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Leaders must invite to a ministry they lead",
            )
        ensure_ministry_manager(db, current_user, payload.ministry_id)

    if payload.ministry_id is not None:
        if db.query(Ministry).filter(Ministry.id == payload.ministry_id).first() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ministry not found"
            )

    if payload.role == UserRole.LEADER and payload.ministry_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A LEADER invite requires a ministry",
        )

    # Os dois campos dizem a mesma coisa: quem é líder global lidera o ministério
    # do convite, e vice-versa. Divergir criaria um meio-líder no cadastro.
    role = payload.role
    ministry_role = payload.ministry_role
    if payload.ministry_id is not None:
        if role == UserRole.LEADER:
            ministry_role = MinistryRole.LEADER
        elif role == UserRole.MEMBER and ministry_role == MinistryRole.LEADER:
            role = UserRole.LEADER

    if payload.email is not None:
        if get_user_by_email(db, payload.email) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already has an account",
            )

    token = generate_token()
    invite = Invite(
        kind=InviteKind.INVITE,
        token_hash=hash_token(token),
        email=payload.email,
        role=role,
        ministry_id=payload.ministry_id,
        ministry_role=ministry_role if payload.ministry_id is not None else None,
        instrument=payload.instrument,
        created_by=current_user.id,
        expires_at=utcnow() + INVITE_TTL,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    return {
        "id": invite.id,
        "token": token,
        "email": invite.email,
        "role": invite.role,
        "ministry_id": invite.ministry_id,
        "ministry_role": invite.ministry_role,
        "instrument": invite.instrument,
        "expires_at": invite.expires_at,
        "created_at": invite.created_at,
    }


@invites_router.get("/", response_model=InviteListResponse)
def list_invites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {UserRole.ADMIN, UserRole.LEADER}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN or LEADER can view invites",
        )

    query = (
        db.query(Invite)
        .options(selectinload(Invite.ministry), selectinload(Invite.creator))
        .filter(Invite.kind == InviteKind.INVITE)
        .filter(Invite.used_at.is_(None))
        .filter(Invite.expires_at > utcnow())
    )
    if current_user.role == UserRole.LEADER:
        query = query.filter(Invite.created_by == current_user.id)

    invites = query.order_by(Invite.created_at.desc()).all()
    return {"total": len(invites), "items": [serialize_invite(i) for i in invites]}


@invites_router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invite = db.query(Invite).filter(Invite.id == invite_id).first()
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )
    if invite.created_by != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator or an ADMIN can cancel this invite",
        )

    db.delete(invite)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
