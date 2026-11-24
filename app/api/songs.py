import re
import unicodedata
from typing import Literal, Optional

from fastapi import Depends, APIRouter, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin, require_song_editor
from app.core.rate_limit import limiter
from app.models.playlist_song import PlaylistSong
from app.models.song import Song
from app.models.song_categories import SONG_CATEGORIES
from app.models.user import User
from app.schemas.song import (
    SongCreate,
    SongImportResponse,
    SongListResponse,
    SongResponse,
    SongUpdate,
    SongViewResponse,
)
from app.services.ai_service import AIInvalidResponseError, AIServiceUnavailableError
from app.services.chordpro import to_plain_lyrics
from app.services.song_import import (
    MAX_IMPORT_BYTES,
    SongImportProvider,
    UnsupportedImportFileError,
    detect_import_file,
    get_song_import_provider,
    import_song,
)
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

def normalize_slides(data: dict, current_song: Song | None = None) -> None:
    """Slides vazios voltam ao automático. Mudou a letra sem mandar slides novos?

    Os slides antigos ficariam com a letra velha no telão, então voltam ao automático.
    """
    if "slides" in data and data["slides"] is not None and not data["slides"].strip():
        data["slides"] = None
    if current_song is None or "slides" in data:
        return
    lyrics_changed = ("chordpro" in data and data["chordpro"] != current_song.chordpro) or (
        "lyrics" in data and data["lyrics"] != current_song.lyrics
    )
    if lyrics_changed:
        data["slides"] = None


def validate_category(data: dict, current: str | None = None) -> None:
    """Só aceita categorias da lista fechada. String vazia vira "sem categoria".

    Uma categoria antiga (texto livre de antes da lista) continua valendo enquanto
    não for trocada, para editar a letra de uma música antiga não dar erro.
    """
    if "category" not in data:
        return
    category = data["category"]
    if category is not None and category.strip() == "":
        data["category"] = None
        return
    if category is None or category in SONG_CATEGORIES or category == current:
        return
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=f"Categoria inválida. Use uma destas: {', '.join(SONG_CATEGORIES)}",
    )


def normalize_title(title: str) -> str:
    decomposed = unicodedata.normalize("NFD", title)
    no_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", no_accents.lower()).split())


# SAME TITLE: aviso "essa música já existe" antes de salvar (ignora acento e caixa).
@songs_router.get("/same-title", response_model=list[SongViewResponse])
def songs_with_same_title(
    title: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wanted = normalize_title(title)
    if not wanted:
        return []
    # O catálogo é pequeno (centenas): comparar em Python evita depender da extensão unaccent.
    songs = db.query(Song).order_by(Song.title, Song.id).all()
    return [song for song in songs if normalize_title(song.title) == wanted]


# CATEGORIES (antes de /{song_id} para não ser lida como id)
@songs_router.get("/categories", response_model=list[str])
def list_song_categories(current_user: User = Depends(get_current_user)):
    return list(SONG_CATEGORIES)


# IMPORT (Fase 1 da projeção): lê o arquivo e devolve o rascunho, sem salvar.
@songs_router.post("/import", response_model=SongImportResponse)
@limiter.limit("20/minute")
async def import_song_file(
    request: Request,
    file: UploadFile = File(...),
    editor: User = Depends(require_song_editor),
    provider: SongImportProvider = Depends(get_song_import_provider),
):
    data = await file.read(MAX_IMPORT_BYTES + 1)
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Arquivo maior que 10 MB.",
        )
    if not data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Arquivo vazio.")

    try:
        import_file = detect_import_file(file.filename, file.content_type, data)
    except UnsupportedImportFileError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc

    try:
        song, used_ai = import_song(import_file, provider)
    except AIServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A leitura automática está indisponível agora. Para PDF e foto, tente de novo em alguns minutos.",
        ) from exc
    except AIInvalidResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não consegui encontrar uma letra nesse arquivo.",
        ) from exc

    return SongImportResponse(
        title=song.title,
        artist=song.artist,
        tone=song.tone,
        chordpro=song.chordpro,
        lyrics=to_plain_lyrics(song.chordpro),
        used_ai=used_ai,
    )


# CREATE
@songs_router.post("/", response_model=SongResponse, status_code=status.HTTP_201_CREATED)
def create_song(payload: SongCreate, db: Session = Depends(get_db), editor: User = Depends(require_song_editor)):
    data = payload.model_dump()
    validate_category(data)
    normalize_slides(data)
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
    category: Optional[str] = None,
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
    if category:
        query = query.filter(Song.category == category)
    total = query.count()

    offset = (page - 1) * limit

    # Sem ORDER BY o Postgres devolve as linhas na ordem física da tabela, que muda
    # quando uma música é editada: a paginação mostrava a mesma música duas vezes.
    songs = (
        query
        .order_by(Song.title, Song.id)
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
    editor: User = Depends(require_song_editor),
):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song Not Found")

    data = payload.model_dump()
    validate_category(data, current=song.category)
    normalize_slides(data)
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

    # Sem isso o banco recusa pela chave estrangeira e a resposta vira 500.
    in_playlist = db.query(PlaylistSong.id).filter(PlaylistSong.song_id == song_id).first()
    if in_playlist is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Song is in a playlist",
        )

    db.delete(song)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# PATCH
@songs_router.patch("/{song_id}", response_model=SongResponse)
def patch_song(song_id: int, payload: SongUpdate, db: Session = Depends(get_db), editor: User = Depends(require_song_editor)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if song is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="song not found")

    update_data = payload.model_dump(exclude_unset=True)
    validate_category(update_data, current=song.category)
    normalize_slides(update_data, current_song=song)
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
