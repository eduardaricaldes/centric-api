from pydantic import BaseModel, EmailStr

from app.models.roles import UserRole

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    prefers_chords: bool = False

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
    prefers_chords: bool

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
