from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, selectinload

from app.api.playlists import get_playlist_or_404
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.playlist_song import PlaylistSong
from app.models.song import Song
from app.models.user import User
from app.schemas.playlist_song import (
    PlaylistSongCreate,
    PlaylistSongReorder,
    PlaylistSongResponse,
    PlaylistSongUpdate,
    PlaylistSongWithSongViewResponse,
)
from app.services.song_views import resolve_song_view, song_for_view
from app.services.permissions import ensure_playlist_manager

playlist_songs_router = APIRouter(
    prefix="/playlist/{playlist_id}/songs",
    tags=["Playlist Songs"],
)


def get_items_ordered(db: Session, playlist_id: int) -> list[PlaylistSong]:
    return (
        db.query(PlaylistSong)
        .filter(PlaylistSong.playlist_id == playlist_id)
        .order_by(PlaylistSong.position)
        .all()
    )


def normalize_positions(items: list[PlaylistSong]) -> None:
    """Garante que as posições fiquem 1, 2, 3... sem buracos nem repetição."""
    for index, item in enumerate(items, start=1):
        if item.position != index:
            item.position = index


# LISTAR MÚSICAS DA PLAYLIST (com a letra, para o dia do culto)
@playlist_songs_router.get(
    "/",
    response_model=list[PlaylistSongWithSongViewResponse],
    response_model_exclude_unset=True,
)
def list_playlist_songs(
    playlist_id: int,
    view: Literal["lyrics", "chords"] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_playlist_or_404(db, playlist_id)

    items = (
        db.query(PlaylistSong)
        .options(selectinload(PlaylistSong.song))
        .filter(PlaylistSong.playlist_id == playlist_id)
        .order_by(PlaylistSong.position)
        .all()
    )

    selected_view = resolve_song_view(view, current_user)
    response = []
    for item in items:
        item_data = PlaylistSongResponse.model_validate(item).model_dump()
        item_data["song"] = song_for_view(item.song, selected_view)
        response.append(item_data)

    return response


# ADICIONAR MÚSICA À PLAYLIST
@playlist_songs_router.post(
    "/",
    response_model=PlaylistSongResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_song_to_playlist(
    playlist_id: int,
    payload: PlaylistSongCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = get_playlist_or_404(db, playlist_id)
    ensure_playlist_manager(db, current_user, playlist)

    song = db.query(Song).filter(Song.id == payload.song_id).first()
    if song is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song not found",
        )

    items = get_items_ordered(db, playlist_id)

    already_added = any(item.song_id == payload.song_id for item in items)
    if already_added:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Song already in this playlist",
        )

    item = PlaylistSong(
        playlist_id=playlist_id,
        song_id=payload.song_id,
        position=len(items) + 1,
    )

    # posição informada: entra no meio e empurra as seguintes
    if payload.position is not None and payload.position <= len(items):
        items.insert(payload.position - 1, item)
        normalize_positions(items)

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


# REORDENAR UMA MÚSICA (mover para outra posição)
@playlist_songs_router.patch("/{item_id}", response_model=list[PlaylistSongResponse])
def move_playlist_song(
    playlist_id: int,
    item_id: int,
    payload: PlaylistSongUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = get_playlist_or_404(db, playlist_id)
    ensure_playlist_manager(db, current_user, playlist)

    items = get_items_ordered(db, playlist_id)
    item = next((i for i in items if i.id == item_id), None)

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song not found in this playlist",
        )

    new_position = min(payload.position, len(items))

    items.remove(item)
    items.insert(new_position - 1, item)
    normalize_positions(items)

    db.commit()

    return get_items_ordered(db, playlist_id)


# REORDENAR A PLAYLIST INTEIRA (drag and drop no front)
@playlist_songs_router.put("/reorder", response_model=list[PlaylistSongResponse])
def reorder_playlist_songs(
    playlist_id: int,
    payload: PlaylistSongReorder,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = get_playlist_or_404(db, playlist_id)
    ensure_playlist_manager(db, current_user, playlist)

    items = get_items_ordered(db, playlist_id)
    items_by_id = {item.id: item for item in items}

    if sorted(payload.item_ids) != sorted(items_by_id.keys()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="item_ids must contain every song of this playlist exactly once",
        )

    normalize_positions([items_by_id[item_id] for item_id in payload.item_ids])
    db.commit()

    return get_items_ordered(db, playlist_id)


# REMOVER MÚSICA DA PLAYLIST (não apaga a música do catálogo)
@playlist_songs_router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_song_from_playlist(
    playlist_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    playlist = get_playlist_or_404(db, playlist_id)
    ensure_playlist_manager(db, current_user, playlist)

    item = (
        db.query(PlaylistSong)
        .filter(
            PlaylistSong.id == item_id,
            PlaylistSong.playlist_id == playlist_id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song not found in this playlist",
        )

    db.delete(item)
    db.flush()

    normalize_positions(get_items_ordered(db, playlist_id))
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
