from pydantic import BaseModel, EmailStr, Field

from app.models.roles import UserRole

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(..., min_length=8)
    prefers_chords: bool = False
    invite_token: str | None = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    prefers_chords: bool

    model_config = {"from_attributes": True}


class UserSummary(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    name: str | None = None
    prefers_chords: bool | None = None


class UserListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[UserResponse]


class UserRoleUpdate(BaseModel):
    role: UserRole

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
