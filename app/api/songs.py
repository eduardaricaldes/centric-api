from typing import Literal, Optional

from fastapi import Depends, APIRouter, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.song import Song
from app.models.user import User
from app.schemas.song import SongCreate, SongListResponse, SongResponse, SongUpdate
from app.services.chordpro import to_plain_lyrics
from app.services.song_views import resolve_song_view, song_detail, song_for_view

songs_router = APIRouter(prefix="/songs", tags=["Songs"])


def resolve_read_view(
    view: Literal["lyrics", "chords"] | None,
    transpose: int | None,
    current_user: User,
) -> Literal["lyrics", "chords"]:
    selected_view = resolve_song_view(view, current_user)
    if transpose is not None and selected_view != "chords":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="transpose is only valid with chords view",
        )
    return selected_view

# CREATE
@songs_router.post("/", response_model=SongResponse, status_code=status.HTTP_201_CREATED)
def create_song(payload: SongCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    data = payload.model_dump()
    if data.get("chordpro"):
        data["lyrics"] = to_plain_lyrics(data["chordpro"])
    song = Song(**data)
    db.add(song)
    db.commit()
    db.refresh(song)
    return song

## payload contém os dados enviados pelo usuário.
## o método model_dump() converte o objeto Pydantic em um dicionário Python.
## ** é usado para desempacotar (unpack) um dicionário em argumentos nomeados ao criar um objeto.
## Depends diz ao FastAPI: Antes de executar esta função, execute outra função e utilize o resultado dela aqui.

# LIST
@songs_router.get(
    "/",
    response_model=SongListResponse,
    response_model_exclude_unset=True,
)
def get_songs(
    search: Optional[str] = None,
    artist: Optional[str] = None,
    view: Literal["lyrics", "chords"] | None = Query(default=None),
    transpose: int | None = Query(default=None, ge=-11, le=11),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
  
):
    selected_view = resolve_read_view(view, transpose, current_user)
    query = db.query(Song)

    if search:
        query = query.filter(Song.title.ilike(f"%{search}%"))
    if artist:
        query = query.filter(Song.artist.ilike(f"%{artist}%"))
    total = query.count()

    if search and total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="music not found"
        ) 
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
        "items": [
            song_for_view(song, selected_view, semitones=transpose)
            for song in songs
        ],
    }


# GET BY ID
@songs_router.get("/{song_id}", response_model=SongResponse)
def get_song(
    song_id: int,
    view: Literal["lyrics", "chords"] | None = Query(default=None),
    transpose: int | None = Query(default=None, ge=-11, le=11),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # O detalhe sempre traz os dois campos para o front alternar sem nova requisição.
    selected_view = resolve_read_view(view, transpose, current_user)
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song Not Found")
    return song_detail(song, selected_view, semitones=transpose)

#.first() do SQLAlchemy retorna o primeiro registro encontrado no filtro 
# SELECT * FROM songs WHERE id = 1 LIMIT 1 - .first() adiciona implicitamente um 
# LIMIT 1 à consulta, tornando eficiente quando esperamos apenas um único resultado.

#O raise é utilizado para lançar uma exceção, interrompendo imediatamente a execução da função.

# UPDATE (PUT)
@songs_router.put("/{song_id}", response_model=SongResponse)
def update_song(
    song_id: int,
    payload: SongCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song Not Found")

    data = payload.model_dump()
    if data.get("chordpro"):
        data["lyrics"] = to_plain_lyrics(data["chordpro"])

    for key, value in data.items():
        setattr(song, key, value)

    db.commit()
    db.refresh(song)
    return song

# DELETE
@songs_router.delete("/{song_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_song(song_id: int, db:Session = Depends(get_db), admin: User = Depends(require_admin)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code= 404, detail="Song not found")
    
    db.delete(song)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# PATCH
@songs_router.patch("/{song_id}", response_model=SongResponse)
def patch_song(song_id: int, payload: SongUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if song is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="song not found")

    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("chordpro"):
        update_data["lyrics"] = to_plain_lyrics(update_data["chordpro"])

    for key, value in update_data.items():
        setattr(song, key, value)

    db.commit()
    db.refresh(song)
    return song

# {
#   "name": "eduarda",
#   "email": "eduarda@example.com",
#   "password": "1234"
# }
