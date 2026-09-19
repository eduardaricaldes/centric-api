from pydantic import BaseModel

from app.models.roles import MinistryRole


class MinistryItem(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class MinistryListResponse(BaseModel):
    total: int
    items: list[MinistryItem]


class MemberResponse(BaseModel):
    user_id: int
    name: str
    role: MinistryRole
    instrument: str | None = None
