from pydantic import BaseModel, Field

from app.schemas.user import UserSummary


class PreachingUpsert(BaseModel):
    preacher_id: int
    theme: str = Field(..., min_length=1, max_length=255)
    bible_reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class PreachingResponse(PreachingUpsert):
    id: int
    event_id: int
    preacher: UserSummary

    model_config = {"from_attributes": True}
