from typing import Literal, TypeAlias

from app.models.song import Song
from app.models.user import User
from app.schemas.song import SongResponse

SongView: TypeAlias = Literal["lyrics", "chords"]


def resolve_song_view(view: SongView | None, current_user: User) -> SongView:
    if view is not None:
        return view
    return "chords" if current_user.is_musician else "lyrics"


def song_for_view(song: Song, view: SongView) -> dict:
    data = SongResponse.model_validate(song).model_dump()

    if view == "lyrics":
        data.pop("chordpro")
    else:
        data["chordpro"] = song.chordpro or song.lyrics
        data.pop("lyrics")

    return data
