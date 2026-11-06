from pydantic import BaseModel, Field

from app.models.roles import MinistryRole


class MinistryItem(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class MinistryListResponse(BaseModel):
    total: int
    items: list[MinistryItem]


class MinistryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class MinistryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class MinistryDetailResponse(BaseModel):
    id: int
    name: str
    description: str | None = None

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    user_id: int
    name: str
    role: MinistryRole
    instrument: str | None = None


class MemberCreate(BaseModel):
    user_id: int
    role: MinistryRole = MinistryRole.MEMBER
    instrument: str | None = None


class MemberUpdate(BaseModel):
    role: MinistryRole | None = None
    instrument: str | None = None
