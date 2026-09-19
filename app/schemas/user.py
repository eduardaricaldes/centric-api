from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    is_musician: bool = False

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    is_musician: bool

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    is_musician: bool

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
