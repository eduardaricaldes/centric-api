from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.event import Event
from app.models.playlist import Playlist
from app.models.roles import UserRole
from app.models.user import User
from app.schemas.playlist import (
    PlaylistCreate,
    PlaylistDetailResponse,
    PlaylistListResponse,
    PlaylistResponse,
    PlaylistUpdate,
)
from app.schemas.playlist_song import PlaylistSongResponse
from app.services.song_views import resolve_song_view, song_for_view
from app.services.permissions import ensure_event_collaborator, ensure_playlist_manager

playlist_router = APIRouter(prefix="/playlist", tags=["Playlists"])


def get_playlist_or_404(db: Session, playlist_id: int) -> Playlist:
    """Busca a playlist ou devolve 404. Reutilizada pelas rotas de músicas da playlist."""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if playlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )
    return playlist


def validate_event_link(
    db: Session,
    event_id: int,
    current_user: User,
    playlist_id: int | None = None,
) -> Event:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    ensure_event_collaborator(db, current_user, event)

    linked_query = db.query(Playlist).filter(Playlist.event_id == event_id)
    if playlist_id is not None:
        linked_query = linked_query.filter(Playlist.id != playlist_id)
    if linked_query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event already has a playlist",
        )
    return event


# CREATE
@playlist_router.post(
    "/",
    response_model=PlaylistResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_playlist(
    payload: PlaylistCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in {UserRole.ADMIN, UserRole.LEADER}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if current_user.role == UserRole.LEADER and payload.event_id is None:
        raise HTTPException(
            status_code=403,
            detail="Leaders must link playlists to an event they manage",
        )
    if payload.event_id is not None:
        validate_event_link(db, payload.event_id, current_user)

    playlist = Playlist(
        title=payload.title,
        date=payload.date,
        description=payload.description,
        event_id=payload.event_id,
        created_by=current_user.id,
    )
    db.add(playlist)
    db.commit()
    db.refresh(playlist)

    return playlist


# LIST
@playlist_router.get("/", response_model=PlaylistListResponse)
def list_playlists(
    search: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Playlist)

    if search:
        query = query.filter(Playlist.title.ilike(f"%{search}%"))

    total = query.count()
    offset = (page - 1) * limit

    playlists = (
        query
        .order_by(Playlist.date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": playlists,
    }


# GET BY ID (com as músicas do culto, na ordem)
@playlist_router.get(
    "/{playlist_id}",
    response_model=PlaylistDetailResponse,
    response_model_exclude_unset=True,
)
def get_playlist(
    playlist_id: int,
    view: Literal["lyrics", "chords"] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = (
        db.query(Playlist)
        .options(selectinload(Playlist.songs))
        .filter(Playlist.id == playlist_id)
        .first()
    )

    if playlist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playlist not found",
        )

    selected_view = resolve_song_view(view, current_user)
    data = PlaylistResponse.model_validate(playlist).model_dump()
    data["songs"] = []

    for item in playlist.songs:
        item_data = PlaylistSongResponse.model_validate(item).model_dump()
        item_data["song"] = song_for_view(item.song, selected_view)
        data["songs"].append(item_data)

    data["total_duration_min"] = sum(
        item.song.duration_min or 0 for item in playlist.songs
    )
    return data


# UPDATE
@playlist_router.put("/{playlist_id}", response_model=PlaylistResponse)
def update_playlist(
    playlist_id: int,
    payload: PlaylistUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = get_playlist_or_404(db, playlist_id)
    ensure_playlist_manager(db, current_user, playlist)

    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("event_id") is not None:
        validate_event_link(
            db,
            update_data["event_id"],
            current_user,
            playlist_id=playlist.id,
        )

    for key, value in update_data.items():
        setattr(playlist, key, value)

    db.commit()
    db.refresh(playlist)

    return playlist


# DELETE
@playlist_router.delete("/{playlist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = get_playlist_or_404(db, playlist_id)
    ensure_playlist_manager(db, current_user, playlist)

    # as músicas da playlist saem junto (cascade), as músicas do catálogo continuam
    db.delete(playlist)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
