from datetime import date as date_type, datetime

from pydantic import BaseModel, Field

from app.schemas.playlist_song import PlaylistSongWithSongResponse


class PlaylistBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    date: date_type
    description: str | None = None


class PlaylistCreate(PlaylistBase):
    pass


class PlaylistUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    date: date_type | None = None
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
    """Playlist com as músicas já ordenadas por position (usado no GET /playlist/{id})."""
    songs: list[PlaylistSongWithSongResponse] = []


class PlaylistListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[PlaylistResponse]
