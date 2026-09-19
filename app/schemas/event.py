from datetime import date as date_type, datetime, time as time_type

from pydantic import BaseModel, Field

from app.models.event import EventStatus, EventType
from app.schemas.assignment import AssignmentDetailResponse
from app.schemas.playlist import PlaylistDetailResponse
from app.schemas.preaching import PreachingResponse


class EventBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    date: date_type
    time: time_type
    type: EventType


class EventCreate(EventBase):
    status: EventStatus = EventStatus.DRAFT


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    date: date_type | None = None
    time: time_type | None = None
    type: EventType | None = None
    status: EventStatus | None = None


class EventResponse(EventBase):
    id: int
    status: EventStatus
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EventWarning(BaseModel):
    code: str
    message: str
    user_id: int
    ministry_ids: list[int]


class EventDetailResponse(EventResponse):
    assignments: list[AssignmentDetailResponse] = Field(default_factory=list)
    preaching: PreachingResponse | None = None
    playlist: PlaylistDetailResponse | None = None
    warnings: list[EventWarning] = Field(default_factory=list)


class EventListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[EventResponse]
