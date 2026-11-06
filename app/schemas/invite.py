from datetime import datetime

from pydantic import BaseModel

from app.models.roles import MinistryRole, UserRole


class InviteCreate(BaseModel):
    email: str | None = None
    role: UserRole = UserRole.MEMBER
    ministry_id: int | None = None
    ministry_role: MinistryRole = MinistryRole.MEMBER
    instrument: str | None = None


class InviteCreateResponse(BaseModel):
    id: int
    token: str
    email: str | None = None
    role: UserRole
    ministry_id: int | None = None
    ministry_role: MinistryRole | None = None
    instrument: str | None = None
    expires_at: datetime
    created_at: datetime


class InviteResponse(BaseModel):
    id: int
    email: str | None = None
    role: UserRole
    ministry_id: int | None = None
    ministry_name: str | None = None
    ministry_role: MinistryRole | None = None
    instrument: str | None = None
    created_by: int
    created_by_name: str
    expires_at: datetime
    created_at: datetime


class InviteListResponse(BaseModel):
    total: int
    items: list[InviteResponse]
