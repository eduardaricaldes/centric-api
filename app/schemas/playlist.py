from datetime import date, datetime
from pydantic import BaseModel, Field

from app.schemas.playlist_song import PlaylistSongResponse


class PlaylistBase(BaseModel):
    title: str = Field(..., min_length=1)
    date: datetime
    description: str | None = None


class PlaylistCreate(PlaylistBase):
    pass


class PlaylistUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    date:datetime | None = None
    description: str | None = None


class PlaylistResponse(PlaylistBase):
    id: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class PlaylistDetailResponse(PlaylistResponse):
    songs: list[PlaylistSongResponse] = []