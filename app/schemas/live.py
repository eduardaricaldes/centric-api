from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LiveUpdate(BaseModel):
    mode: Literal["slide", "black", "logo"]
    song_index: int | None = Field(default=None, ge=0)
    slide_index: int | None = Field(default=None, ge=0)
    song_title: str | None = Field(default=None, max_length=255)
    lines: list[str] = Field(default_factory=list, max_length=40)


class LiveStateResponse(BaseModel):
    """Público: só o slide do telão. Nada de pessoas ou escala."""

    mode: Literal["slide", "black", "logo"]
    song_index: int | None = None
    slide_index: int | None = None
    song_title: str | None = None
    lines: list[str] = Field(default_factory=list)
    version: int
    updated_at: datetime | None = None
