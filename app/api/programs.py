from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.events import get_event_or_404
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.playlist import Playlist
from app.models.playlist_song import PlaylistSong
from app.models.program_suggestion import ProgramSuggestion
from app.models.user import User
from app.schemas.program import (
    ProgramApplyRequest,
    ProgramApplyResponse,
    ProgramBlockType,
    ProgramDraft,
    ProgramSuggestRequest,
    ProgramSuggestionResponse,
)
from app.services.ai_service import (
    AIInvalidResponseError,
    AIServiceUnavailableError,
    ProgramSuggestionProvider,
    get_program_suggestion_provider,
)
from app.services.permissions import ensure_event_collaborator
from app.services.programs import (
    ProgramValidationError,
    build_program_context,
    get_request_hash,
    validate_and_enrich_program,
)

programs_router = APIRouter(
    prefix="/events/{event_id}/program",
    tags=["Event Program"],
)


def serialize_suggestion(
    suggestion: ProgramSuggestion,
    *,
    cached: bool,
) -> dict:
    draft = ProgramDraft.model_validate(suggestion.response)
    data = draft.model_dump(mode="json")
    data.update(
        suggestion_id=suggestion.id,
        event_id=suggestion.event_id,
        briefing=suggestion.briefing,
        duracao_alvo_min=suggestion.duration_minutes,
        provider_model=suggestion.provider_model,
        cached=cached,
        created_at=suggestion.created_at,
        applied_at=suggestion.applied_at,
    )
    return data


@programs_router.post(
    "/suggest",
    response_model=ProgramSuggestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def suggest_program(
    event_id: int,
    payload: ProgramSuggestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: ProgramSuggestionProvider = Depends(get_program_suggestion_provider),
):
    event = get_event_or_404(db, event_id)
    ensure_event_collaborator(db, current_user, event)
    context = build_program_context(
        db,
        event,
        payload.briefing,
        payload.duracao_alvo_min,
    )
    if not context["catalog"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Song catalog is empty",
        )

    request_hash = get_request_hash(context, provider.model_name)
    cached = (
        db.query(ProgramSuggestion)
        .filter(ProgramSuggestion.request_hash == request_hash)
        .first()
    )
    if cached is not None:
        return serialize_suggestion(cached, cached=True)

    try:
        draft = provider.suggest(context)
        draft = validate_and_enrich_program(draft, context)
    except AIServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI suggestion is unavailable; continue in manual mode",
        ) from exc
    except (AIInvalidResponseError, ProgramValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI returned an invalid program: {exc}",
        ) from exc

    suggestion = ProgramSuggestion(
        event_id=event.id,
        briefing=payload.briefing,
        duration_minutes=payload.duracao_alvo_min,
        response=draft.model_dump(mode="json"),
        request_hash=request_hash,
        provider_model=provider.model_name,
        requested_by=current_user.id,
    )
    db.add(suggestion)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        cached = (
            db.query(ProgramSuggestion)
            .filter(ProgramSuggestion.request_hash == request_hash)
            .first()
        )
        if cached is not None:
            return serialize_suggestion(cached, cached=True)
        raise

    db.refresh(suggestion)
    return serialize_suggestion(suggestion, cached=False)


@programs_router.post(
    "/apply",
    response_model=ProgramApplyResponse,
)
def apply_program(
    event_id: int,
    payload: ProgramApplyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = get_event_or_404(db, event_id)
    ensure_event_collaborator(db, current_user, event)
    suggestion = (
        db.query(ProgramSuggestion)
        .filter(
            ProgramSuggestion.id == payload.suggestion_id,
            ProgramSuggestion.event_id == event.id,
        )
        .first()
    )
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Program suggestion not found")
    if suggestion.applied_at is not None:
        raise HTTPException(status_code=409, detail="Program suggestion already applied")

    draft = payload.programacao or ProgramDraft.model_validate(suggestion.response)
    context = build_program_context(
        db,
        event,
        suggestion.briefing,
        suggestion.duration_minutes,
    )
    try:
        draft = validate_and_enrich_program(draft, context)
    except ProgramValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    playlist = db.query(Playlist).filter(Playlist.event_id == event.id).first()
    if playlist is None:
        playlist = Playlist(
            title=f"Programação — {event.title}",
            date=event.date,
            description="Playlist aplicada a partir de sugestão revisada.",
            event_id=event.id,
            created_by=current_user.id,
        )
        db.add(playlist)
        db.flush()
    else:
        playlist.date = event.date
        db.query(PlaylistSong).filter(
            PlaylistSong.playlist_id == playlist.id
        ).delete(synchronize_session=False)

    song_ids = [
        int(block.song_id)
        for block in draft.blocos
        if block.tipo == ProgramBlockType.MUSIC and block.song_id is not None
    ]
    db.add_all(
        PlaylistSong(playlist_id=playlist.id, song_id=song_id, position=position)
        for position, song_id in enumerate(song_ids, start=1)
    )

    applied_at = datetime.now(timezone.utc)
    suggestion.applied_response = draft.model_dump(mode="json")
    suggestion.applied_at = applied_at
    suggestion.applied_by = current_user.id
    suggestion.playlist_id = playlist.id
    db.commit()

    return {
        "suggestion_id": suggestion.id,
        "playlist_id": playlist.id,
        "song_ids": song_ids,
        "applied_at": applied_at,
    }
