from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

class SongBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    lyrics: str = Field(..., min_length=1)
    artist: Optional[str] = None,Field(default=None, max_length=255)
    tone: Optional[str] = None, Field(default=None, max_length=50)
    category: Optional[str] = None,Field(default=None, max_length=100)

class SongCreate(SongBase):
    pass

class SongUpdate(BaseModel):
    title:Optional[str] = None
    artist:Optional[str] = None
    lyrics:Optional[str] = None
    tone: Optional[str] = None
    category: Optional[str] = None

class SongResponse(SongBase):
    id:int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class SongListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[SongResponse]