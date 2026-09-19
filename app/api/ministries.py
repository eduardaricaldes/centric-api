from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.ministry import Ministry
from app.models.ministry_member import MinistryMember
from app.models.roles import UserRole
from app.models.user import User
from app.schemas.ministry import MemberResponse, MinistryListResponse

ministries_router = APIRouter(prefix="/ministries", tags=["Ministries"])


@ministries_router.get("/", response_model=MinistryListResponse)
def list_ministries(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LEADER)),
):
    ministries = db.query(Ministry).order_by(Ministry.name).all()
    return {"total": len(ministries), "items": ministries}


@ministries_router.get("/{ministry_id}/members", response_model=list[MemberResponse])
def list_ministry_members(
    ministry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LEADER)),
):
    if db.query(Ministry).filter(Ministry.id == ministry_id).first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ministry not found",
        )

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
