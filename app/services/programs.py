import hashlib
import json
from datetime import timedelta

from sqlalchemy.orm import Session, selectinload

from app.models.assignment import Assignment
from app.models.event import Event
from app.models.playlist import Playlist
from app.models.playlist_song import PlaylistSong
from app.models.song import Song
from app.schemas.program import ProgramBlockType, ProgramDraft

RECENT_HISTORY_DAYS = 28


class ProgramValidationError(ValueError):
    pass


def build_program_context(
    db: Session,
    event: Event,
    briefing: str,
    duration_minutes: int,
) -> dict:
    songs = db.query(Song).order_by(Song.id).all()
    assignments = (
        db.query(Assignment)
        .options(
            selectinload(Assignment.user),
            selectinload(Assignment.ministry),
        )
        .filter(Assignment.event_id == event.id)
        .order_by(Assignment.id)
        .all()
    )
    history_start = event.date - timedelta(days=RECENT_HISTORY_DAYS)
    history_rows = (
        db.query(PlaylistSong, Song, Event)
        .join(Playlist, Playlist.id == PlaylistSong.playlist_id)
        .join(Event, Event.id == Playlist.event_id)
        .join(Song, Song.id == PlaylistSong.song_id)
        .filter(Event.date >= history_start, Event.date < event.date)
        .order_by(Event.date.desc(), PlaylistSong.position)
        .all()
    )

    preaching = event.preaching
    return {
        "event": {
            "id": event.id,
            "title": event.title,
            "date": event.date.isoformat(),
            "time": event.time.isoformat(),
            "type": event.type.value,
            "preaching": (
                {
                    "theme": preaching.theme,
                    "bible_reference": preaching.bible_reference,
                }
                if preaching is not None
                else None
            ),
        },
        "briefing": briefing,
        "target_duration_minutes": duration_minutes,
        "catalog": [
            {
                "id": song.id,
                "title": song.title,
                "tone": song.tone,
                "category": song.category,
            }
            for song in songs
        ],
        "assignments": [
            {
                "user": assignment.user.name,
                "ministry": assignment.ministry.name,
                "function": assignment.function,
                "status": assignment.status.value,
            }
            for assignment in assignments
        ],
        "recent_song_history": [
            {
                "song_id": song.id,
                "title": song.title,
                "event_id": previous_event.id,
                "event_date": previous_event.date.isoformat(),
            }
            for _item, song, previous_event in history_rows
        ],
    }


def get_request_hash(context: dict, model_name: str) -> str:
    payload = {"model": model_name, "context": context}
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_and_enrich_program(draft: ProgramDraft, context: dict) -> ProgramDraft:
    catalog = {song["id"]: song for song in context["catalog"]}
    music_blocks = [
        block for block in draft.blocos if block.tipo == ProgramBlockType.MUSIC
    ]
    song_ids = [block.song_id for block in music_blocks]

    if not song_ids:
        raise ProgramValidationError("Program must contain at least one song")
    unknown_ids = sorted(song_id for song_id in song_ids if song_id not in catalog)
    if unknown_ids:
        raise ProgramValidationError(f"Unknown song_id values: {unknown_ids}")
    if len(song_ids) != len(set(song_ids)):
        raise ProgramValidationError("Program cannot repeat the same song")

    total_duration = sum(block.duracao_min for block in draft.blocos)
    target_duration = context["target_duration_minutes"]
    if total_duration != target_duration:
        raise ProgramValidationError(
            f"Program duration is {total_duration}, expected {target_duration}"
        )

    enriched = draft.model_copy(deep=True)
    existing_alerts = set(enriched.alertas)
    recent_by_song: dict[int, dict] = {}
    for usage in context["recent_song_history"]:
        recent_by_song.setdefault(usage["song_id"], usage)

    for song_id in song_ids:
        usage = recent_by_song.get(song_id)
        if usage is None:
            continue
        alert = (
            f"A música {catalog[song_id]['title']} foi usada em "
            f"{usage['event_date']}."
        )
        if alert not in existing_alerts:
            enriched.alertas.append(alert)
            existing_alerts.add(alert)

    return enriched
