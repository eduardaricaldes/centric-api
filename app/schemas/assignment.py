from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field

from app.models.assignment import AssignmentStatus
from app.schemas.user import UserSummary


class MinistrySummary(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class AssignmentCreate(BaseModel):
    user_id: int
    ministry_id: int
    function: str = Field(..., min_length=1, max_length=100)
    notes: str | None = None


class AssignmentUpdate(BaseModel):
    user_id: int | None = None
    ministry_id: int | None = None
    function: str | None = Field(default=None, min_length=1, max_length=100)
    notes: str | None = None


class AssignmentRespond(BaseModel):
    status: Literal[AssignmentStatus.CONFIRMED, AssignmentStatus.DECLINED]


class AssignmentResponse(BaseModel):
    id: int
    event_id: int
    user_id: int
    ministry_id: int
    function: str
    status: AssignmentStatus
    responded_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssignmentDetailResponse(AssignmentResponse):
    user: UserSummary
    ministry: MinistrySummary


class MyAssignmentResponse(AssignmentResponse):
    event_title: str
    event_date: date
    event_time: time
