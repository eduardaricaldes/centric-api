import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.dependencies import get_current_user, require_admin
from app.main import app
from app.models.user import User

_DB_URL = os.environ.get("DATABASE_URL", "postgresql://dev_user:dev_password@localhost:5432/centric_db")

os.environ.setdefault("DATABASE_URL", _DB_URL)
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")


@pytest.fixture()
def db_session():
    engine = create_engine(_DB_URL)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    session.add(
        User(
            id=1,
            name="Admin",
            email="admin@comunidadenorth.com",
            password_hash="x",
            role="ADMIN",
        )
    )
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def client(db_session):
    admin = db_session.get(User, 1)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[require_admin] = lambda: admin

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def song_ids(client):
    ids = []
    for title in ["Ousado Amor", "Descansarei", "Bondade de Deus", "Eu Navegarei"]:
        response = client.post(
            "/songs/",
            json={
                "title": title,
                "lyrics": f"letra de {title}",
                "artist": "Isaias Saad",
                "tone": "G",
                "category": "Adoração",
            },
        )
        ids.append(response.json()["id"])
    return ids


@pytest.fixture()
def playlist_id(client):
    response = client.post(
        "/playlist/",
        json={
            "title": "Culto de Domingo à Noite",
            "date": "2026-05-26",
            "description": "Culto de celebração",
        },
    )
    return response.json()["id"]
