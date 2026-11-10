from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from app.models.share_link import ShareLinkKind


class ShareLinkCreate(BaseModel):
    song_id: int | None = None
    event_id: int | None = None

    @model_validator(mode="after")
    def exactly_one_target(self) -> "ShareLinkCreate":
        if (self.song_id is None) == (self.event_id is None):
            raise ValueError("Informe song_id ou event_id, só um dos dois")
        return self


class ShareLinkResponse(BaseModel):
    id: int
    token: str
    kind: ShareLinkKind
    song_id: int | None = None
    event_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ShareLinkListResponse(BaseModel):
    total: int
    items: list[ShareLinkResponse]


# Respostas públicas: só o que se lê numa folha de letra. Os modelos listam
# cada campo de propósito, para nada de pessoas, escalas ou e-mails escapar.
class PublicSong(BaseModel):
    title: str
    artist: str | None = None
    tone: str | None = None
    lyrics: str
    chordpro: str | None = None


class PublicSongShare(BaseModel):
    kind: Literal["song"] = "song"
    song: PublicSong


class PublicEventShare(BaseModel):
    kind: Literal["event"] = "event"
    title: str
    date: date
    songs: list[PublicSong]
