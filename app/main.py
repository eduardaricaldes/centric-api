from fastapi import FastAPI
from sqlalchemy import text


from app.api.songs import songs_router
from app.core.database import engine

app = FastAPI(title="Centric API")


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