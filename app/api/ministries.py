from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin, require_roles
from app.models.ministry import Ministry
from app.models.ministry_member import MinistryMember
from app.models.roles import MinistryRole, UserRole
from app.models.user import User
from app.schemas.ministry import (
    MemberCreate,
    MemberResponse,
    MemberUpdate,
    MinistryCreate,
    MinistryDetailResponse,
    MinistryListResponse,
    MinistryUpdate,
)
from app.services.memberships import sync_global_role
from app.services.permissions import ensure_ministry_manager

ministries_router = APIRouter(prefix="/ministries", tags=["Ministries"])


def get_ministry_or_404(db: Session, ministry_id: int) -> Ministry:
    ministry = db.query(Ministry).filter(Ministry.id == ministry_id).first()
    if ministry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ministry not found",
        )
    return ministry


def get_membership_or_404(db: Session, ministry_id: int, user_id: int) -> MinistryMember:
    membership = (
        db.query(MinistryMember)
        .filter(
            MinistryMember.ministry_id == ministry_id,
            MinistryMember.user_id == user_id,
        )
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ministry member not found",
        )
    return membership


def check_name_unique(db: Session, name: str, ignore_id: int | None = None) -> None:
    query = db.query(Ministry).filter(Ministry.name == name)
    if ignore_id is not None:
        query = query.filter(Ministry.id != ignore_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ministry name already in use",
        )


@ministries_router.get("/", response_model=MinistryListResponse)
def list_ministries(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LEADER)),
):
    ministries = db.query(Ministry).order_by(Ministry.name).all()
    return {"total": len(ministries), "items": ministries}


@ministries_router.post(
    "/",
    response_model=MinistryDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ministry(
    payload: MinistryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    check_name_unique(db, payload.name)

    ministry = Ministry(**payload.model_dump())
    db.add(ministry)
    db.commit()
    db.refresh(ministry)
    return ministry


@ministries_router.patch("/{ministry_id}", response_model=MinistryDetailResponse)
def update_ministry(
    ministry_id: int,
    payload: MinistryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    ministry = get_ministry_or_404(db, ministry_id)

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        check_name_unique(db, updates["name"], ignore_id=ministry_id)

    for key, value in updates.items():
        setattr(ministry, key, value)

    db.commit()
    db.refresh(ministry)
    return ministry


@ministries_router.get("/{ministry_id}/members", response_model=list[MemberResponse])
def list_ministry_members(
    ministry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LEADER)),
):
    get_ministry_or_404(db, ministry_id)

    members = (
        db.query(MinistryMember)
        .options(selectinload(MinistryMember.user))
        .filter(MinistryMember.ministry_id == ministry_id)
        .order_by(MinistryMember.id)
        .all()
    )
    return [
        {
            "user_id": m.user_id,
            "name": m.user.name,
            "role": m.role,
            "instrument": m.instrument,
        }
        for m in members
    ]


@ministries_router.post(
    "/{ministry_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_ministry_member(
    ministry_id: int,
    payload: MemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_ministry_or_404(db, ministry_id)
    ensure_ministry_manager(db, current_user, ministry_id)

    if payload.role == MinistryRole.LEADER and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN can set a member as LEADER",
        )

    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = (
        db.query(MinistryMember)
        .filter(
            MinistryMember.ministry_id == ministry_id,
            MinistryMember.user_id == payload.user_id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this ministry",
        )

    membership = MinistryMember(
        ministry_id=ministry_id,
        user_id=payload.user_id,
        role=payload.role,
        instrument=payload.instrument,
    )
    db.add(membership)
    db.flush()
    sync_global_role(db, target_user)
    db.commit()
    db.refresh(membership)

    return {
        "user_id": membership.user_id,
        "name": target_user.name,
        "role": membership.role,
        "instrument": membership.instrument,
    }


@ministries_router.patch(
    "/{ministry_id}/members/{user_id}",
    response_model=MemberResponse,
)
def update_ministry_member(
    ministry_id: int,
    user_id: int,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_ministry_or_404(db, ministry_id)
    ensure_ministry_manager(db, current_user, ministry_id)
    membership = get_membership_or_404(db, ministry_id, user_id)

    updates = payload.model_dump(exclude_unset=True)

    if updates.get("role") == MinistryRole.LEADER and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN can set a member as LEADER",
        )

    if "instrument" in updates:
        membership.instrument = updates["instrument"]
    if "role" in updates:
        membership.role = updates["role"]

    db.flush()
    sync_global_role(db, membership.user)
    db.commit()
    db.refresh(membership)

    return {
        "user_id": membership.user_id,
        "name": membership.user.name,
        "role": membership.role,
        "instrument": membership.instrument,
    }


@ministries_router.delete(
    "/{ministry_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_ministry_member(
    ministry_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_ministry_or_404(db, ministry_id)
    ensure_ministry_manager(db, current_user, ministry_id)
    membership = get_membership_or_404(db, ministry_id, user_id)

    user = membership.user
    db.delete(membership)
    db.flush()
    sync_global_role(db, user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
