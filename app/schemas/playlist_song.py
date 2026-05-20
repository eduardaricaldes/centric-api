from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.song import SongResponse


class PlaylistSongBase(BaseModel):
    song_id: int
    position: int = Field(..., ge=1)


class PlaylistSongCreate(PlaylistSongBase):
    pass


class PlaylistSongUpdate(BaseModel):
    position: int = Field(..., ge=1)


class PlaylistSongResponse(BaseModel):
    id: int
    playlist_id: int
    song_id: int
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class PlaylistSongWithSongResponse(PlaylistSongResponse):
    song: SongResponse