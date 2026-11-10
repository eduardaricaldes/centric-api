import secrets

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.models.event import Event
from app.models.playlist import Playlist
from app.models.playlist_song import PlaylistSong
from app.models.share_link import ShareLink, ShareLinkKind
from app.models.song import Song
from app.models.user import User
from app.schemas.share_link import (
    PublicEventShare,
    PublicSong,
    PublicSongShare,
    ShareLinkCreate,
    ShareLinkListResponse,
    ShareLinkResponse,
)
from app.services.invites import utcnow
from app.services.permissions import ensure_share_link_manager

TOKEN_NBYTES = 32

share_links_router = APIRouter(prefix="/share-links", tags=["Share links"])
public_router = APIRouter(prefix="/public", tags=["Public"])


def generate_share_token() -> str:
    return secrets.token_urlsafe(TOKEN_NBYTES)


def load_target(
    db: Session, song_id: int | None, event_id: int | None
) -> tuple[Song | None, Event | None]:
    if song_id is not None:
        song = db.query(Song).filter(Song.id == song_id).first()
        if song is None:
            raise HTTPException(status_code=404, detail="Song not found")
        return song, None

    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return None, event


def active_links_query(db: Session, song_id: int | None, event_id: int | None):
    query = db.query(ShareLink).filter(ShareLink.revoked_at.is_(None))
    if song_id is not None:
        return query.filter(ShareLink.song_id == song_id)
    return query.filter(ShareLink.event_id == event_id)


@share_links_router.post(
    "/",
    response_model=ShareLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_share_link(
    payload: ShareLinkCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cria o link, ou devolve o que já está ativo para a mesma música/evento."""
    _, event = load_target(db, payload.song_id, payload.event_id)
    ensure_share_link_manager(db, current_user, event=event)

    existing = (
        active_links_query(db, payload.song_id, payload.event_id)
        .order_by(ShareLink.created_at.desc())
        .first()
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing

    link = ShareLink(
        token=generate_share_token(),
        kind=ShareLinkKind.SONG if payload.song_id is not None else ShareLinkKind.EVENT,
        song_id=payload.song_id,
        event_id=payload.event_id,
        created_by=current_user.id,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@share_links_router.get("/", response_model=ShareLinkListResponse)
def list_share_links(
    song_id: int | None = Query(default=None),
    event_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Links ativos de uma música ou de um evento."""
    if (song_id is None) == (event_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe song_id ou event_id, só um dos dois",
        )
    _, event = load_target(db, song_id, event_id)
    ensure_share_link_manager(db, current_user, event=event)

    links = (
        active_links_query(db, song_id, event_id)
        .order_by(ShareLink.created_at.desc())
        .all()
    )
    return {"total": len(links), "items": links}


@share_links_router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    link = (
        db.query(ShareLink)
        .options(selectinload(ShareLink.event))
        .filter(ShareLink.id == link_id, ShareLink.revoked_at.is_(None))
        .first()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Share link not found")
    ensure_share_link_manager(db, current_user, event=link.event)

    link.revoked_at = utcnow()
    link.revoked_by = current_user.id
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def public_song(song: Song) -> PublicSong:
    return PublicSong(
        title=song.title,
        artist=song.artist,
        tone=song.tone,
        lyrics=song.lyrics,
        chordpro=song.chordpro,
    )


@public_router.get(
    "/share/{token}",
    response_model=PublicSongShare | PublicEventShare,
)
@limiter.limit("60/minute")
def read_share_link(
    request: Request,
    response: Response,
    token: str = Path(min_length=16, max_length=64),
    db: Session = Depends(get_db),
):
    """Leitura sem login. Link revogado ou desconhecido responde 404, igual."""
    # O link pode ser revogado a qualquer hora: nada de cache em CDN ou navegador.
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"

    link = (
        db.query(ShareLink)
        .filter(ShareLink.token == token, ShareLink.revoked_at.is_(None))
        .first()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    if link.kind == ShareLinkKind.SONG:
        return PublicSongShare(song=public_song(link.song))

    event = (
        db.query(Event)
        .options(
            selectinload(Event.playlist)
            .selectinload(Playlist.songs)
            .selectinload(PlaylistSong.song)
        )
        .filter(Event.id == link.event_id)
        .first()
    )
    songs = [public_song(item.song) for item in event.playlist.songs] if event.playlist else []
    return PublicEventShare(title=event.title, date=event.date, songs=songs)
