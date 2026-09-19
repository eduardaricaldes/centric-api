from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.playlist import Playlist
from app.models.user import User
from app.schemas.playlist import (
    PlaylistCreate,
    PlaylistDetailResponse,
    PlaylistListResponse,
    PlaylistResponse,
    PlaylistUpdate,
)

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


# CREATE
@playlist_router.post(
    "/",
    response_model=PlaylistResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_playlist(
    payload: PlaylistCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    playlist = Playlist(
        title=payload.title,
        date=payload.date,
        description=payload.description,
        created_by=admin.id,
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
@playlist_router.get("/{playlist_id}", response_model=PlaylistDetailResponse)
def get_playlist(
    playlist_id: int,
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

    return playlist


# UPDATE
@playlist_router.put("/{playlist_id}", response_model=PlaylistResponse)
def update_playlist(
    playlist_id: int,
    payload: PlaylistUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    playlist = get_playlist_or_404(db, playlist_id)

    update_data = payload.model_dump(exclude_unset=True)

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
    admin: User = Depends(require_admin),
):
    playlist = get_playlist_or_404(db, playlist_id)

    # as músicas da playlist saem junto (cascade), as músicas do catálogo continuam
    db.delete(playlist)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
