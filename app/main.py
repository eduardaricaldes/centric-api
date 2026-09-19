from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.songs import songs_router
from app.core.config import settings
from app.core.database import engine
from app.api.auth import router as auth_router
from app.api.playlists import playlist_router
from app.api.playlist_songs import playlist_songs_router

app = FastAPI(title="Centric API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Centric API is running!"}


@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"database": "ok"}


# Inclusão das rotas de songs
app.include_router(songs_router)
app.include_router(auth_router)
app.include_router(playlist_router)
app.include_router(playlist_songs_router)

