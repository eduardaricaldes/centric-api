from typing import Literal, TypeAlias

from app.models.song import Song
from app.models.user import User
from app.schemas.song import SongResponse
from app.services.chordpro import transpose as transpose_chordpro

SongView: TypeAlias = Literal["lyrics", "chords"]


def resolve_song_view(view: SongView | None, current_user: User) -> SongView:
    if view is not None:
        return view
    return "chords" if current_user.is_musician else "lyrics"


def _transpose_tone(tone: str | None, semitones: int) -> str | None:
    if tone is None:
        return None
    return transpose_chordpro(f"[{tone}]", semitones)[1:-1]


def _apply_chord_view(data: dict, song: Song, semitones: int | None) -> None:
    chordpro = song.chordpro or song.lyrics
    if semitones is not None:
        chordpro = transpose_chordpro(chordpro, semitones)
        data["tone"] = _transpose_tone(song.tone, semitones)
    data["chordpro"] = chordpro


def song_for_view(
    song: Song,
    view: SongView,
    semitones: int | None = None,
) -> dict:
    data = SongResponse.model_validate(song).model_dump()

    if view == "lyrics":
        data.pop("chordpro")
    else:
        _apply_chord_view(data, song, semitones)
        data.pop("lyrics")

    return data


def song_detail(
    song: Song,
    view: SongView,
    semitones: int | None = None,
) -> dict:
    data = SongResponse.model_validate(song).model_dump()
    if view == "chords":
        _apply_chord_view(data, song, semitones)
    return data
