from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.song import SongResponse, SongViewResponse


class PlaylistSongBase(BaseModel):
    song_id: int
    position: int | None = Field(default=None, ge=1)


class PlaylistSongCreate(PlaylistSongBase):
    """position é opcional: quando não informada, a música vai para o fim da playlist."""
    pass


class PlaylistSongUpdate(BaseModel):
    position: int = Field(..., ge=1)


class PlaylistSongReorder(BaseModel):
    """Ordem final desejada: lista de ids de playlist_songs na sequência do culto."""
    item_ids: list[int] = Field(..., min_length=1)


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


class PlaylistSongWithSongViewResponse(PlaylistSongResponse):
    song: SongViewResponse
