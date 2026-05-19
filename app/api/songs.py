from typing import Optional

from fastapi import Depends, FastAPI, APIRouter, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.models.song import Song
from app.schemas.song import SongCreate, SongListResponse, SongResponse, SongUpdate

songs_router = APIRouter(prefix="/songs", tags=["Songs"])

# CREATE
@songs_router.post("/", response_model=SongResponse, status_code=status.HTTP_201_CREATED)
def create_song(payload: SongCreate, db:Session = Depends (get_db)):
    song = Song(**payload.model_dump())
    db.add(song)
    db.commit()
    db.refresh(song) 
    return song

## payload contém os dados enviados pelo usuário.
## o método model_dump() converte o objeto Pydantic em um dicionário Python.
## ** é usado para desempacotar (unpack) um dicionário em argumentos nomeados ao criar um objeto.
## Depends diz ao FastAPI: Antes de executar esta função, execute outra função e utilize o resultado dela aqui.

# LIST
@songs_router.get("/", response_model=SongListResponse)
def get_songs(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(Song)

    if search:
        query = query.filter(Song.title.ilike(f"%{search}%"))
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
        "items": songs
    }


# GET BY ID
@songs_router.get("/{song_id}", response_model = SongResponse)
def get_song(song_id:int, db:Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song Not Found")
    return song

#.first() do SQLAlchemy retorna o primeiro registro encontrado no filtro 
# SELECT * FROM songs WHERE id = 1 LIMIT 1 - .first() adiciona implicitamente um 
# LIMIT 1 à consulta, tornando eficiente quando esperamos apenas um único resultado.

#O raise é utilizado para lançar uma exceção, interrompendo imediatamente a execução da função.

# UPDATE (PUT)
@songs_router.put("/{song_id}", response_model= SongResponse)
def update_song(song_id:int, payload: SongUpdate, db:Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code=404, detail="Song Not Found")
    for key, value in payload.model_dump(exclude_unset=True).items(): # entender melhor 
        setattr(song, key, value)
    
    db.commit()
    db.refresh(song)
    return song

# DELETE
@songs_router.delete("/{song_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_song(song_id: int, db:Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if not song:
        raise HTTPException(status_code= 404, detail="Song not found")
    
    db.delete(song)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@songs_router.patch("/{song_id}", response_model=SongResponse)
def patch_song(song_id: int, payload: SongUpdate, db:Session = Depends(get_db)):
    song = db.query(Song).filter(Song.id == song_id).first()
    if song is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="song not found"
        )

    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(song, key, value)

    db.commit()
    db.refresh(song)

    return song