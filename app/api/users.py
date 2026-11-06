from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_roles
from app.models.invite import Invite, InviteKind
from app.models.roles import UserRole
from app.models.user import User
from app.schemas.password import PasswordResetTokenResponse
from app.schemas.user import UserListResponse, UserResponse, UserRoleUpdate
from app.services.invites import PASSWORD_RESET_TTL, generate_token, hash_token, utcnow
from app.services.permissions import ensure_password_reset_allowed

users_router = APIRouter(prefix="/users", tags=["Users"])


@users_router.get("/", response_model=UserListResponse)
def list_users(
    search: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LEADER)),
):
    query = db.query(User)
    if search:
        pattern = f"%{search}%"
        query = query.filter(or_(User.name.ilike(pattern), User.email.ilike(pattern)))

    total = query.count()
    items = (
        query.order_by(User.name)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {"total": total, "page": page, "limit": limit, "items": items}


@users_router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target.id == current_user.id and payload.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An admin cannot demote themselves",
        )

    if target.role == UserRole.ADMIN and payload.role != UserRole.ADMIN:
        remaining_admins = (
            db.query(User)
            .filter(User.role == UserRole.ADMIN, User.id != target.id)
            .count()
        )
        if remaining_admins == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the last admin",
            )

    target.role = payload.role
    db.commit()
    db.refresh(target)
    return target


@users_router.post(
    "/{user_id}/reset-password",
    response_model=PasswordResetTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_password_reset(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LEADER)),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    ensure_password_reset_allowed(db, current_user, target)

    token = generate_token()
    invite = Invite(
        kind=InviteKind.PASSWORD_RESET,
        token_hash=hash_token(token),
        email=target.email,
        created_by=current_user.id,
        expires_at=utcnow() + PASSWORD_RESET_TTL,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return {"token": token, "expires_at": invite.expires_at}
