from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

class SongBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    lyrics: str = Field(..., min_length=1)
    chordpro: Optional[str] = None
    artist: Optional[str] = Field(default=None, max_length=255)
    tone: Optional[str] = Field(default=None, max_length=50)
    category: Optional[str] = Field(default=None, max_length=100)

class SongCreate(SongBase):
    pass

class SongUpdate(BaseModel):
    title: Optional[str] = None
    lyrics: Optional[str] = None
    chordpro: Optional[str] = None
    artist: Optional[str] = None
    tone: Optional[str] = None
    category: Optional[str] = None

class SongResponse(SongBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SongViewResponse(BaseModel):
    id: int
    title: str
    artist: Optional[str] = None
    lyrics: Optional[str] = None
    chordpro: Optional[str] = None
    tone: Optional[str] = None
    category: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class SongListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[SongViewResponse]
