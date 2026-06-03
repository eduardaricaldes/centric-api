from fastapi import Depends, APIRouter, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import  get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.playlist import Playlist
from app.models.user import User
from app.schemas.playlist import PlaylistBase,PlaylistCreate,PlaylistResponse

playlist_router= APIRouter(prefix="/playlist", tags=["playlist"])

@playlist_router.post("/", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
def create_playlist(payload: PlaylistCreate, db:Session = Depends (get_db), admin: User = Depends(require_admin)
):
    playlist = Playlist(
        title=payload.title, 
        date=payload.date,
        description=payload.description,
        created_by=admin.id
        )
    db.add(playlist)
    db.commit()
    db.refresh(playlist)

    return playlist

@playlist_router.get("/", response_model=PlaylistResponse)
def get_playlist(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
  
):
    query = db.query(Song)

    offset = (page - 1) * limit

    songs = (
        query
        .offset(offset)
        .limit(limit)
        .all()
    )


    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": songs
    }

