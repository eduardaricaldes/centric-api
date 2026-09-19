import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.dependencies import get_current_user, require_admin
from app.main import app
from app.models.roles import UserRole
from app.models.user import User

ADMIN_EMAIL = "admin@comunidadenorth.com"

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://dev_user:dev_password@localhost:5432/centric_test",
)

# Trava de segurança: os testes limpam TODAS as tabelas do banco que usam.
# Se isso apontar para o banco de desenvolvimento, o repertório da igreja vai embora.
if make_url(TEST_DATABASE_URL).database == make_url(settings.database_url).database:
    raise RuntimeError(
        "TEST_DATABASE_URL aponta para o mesmo banco do DATABASE_URL "
        f"({make_url(settings.database_url).database}). Os testes apagam todas as "
        "tabelas do banco que usam. Configure um banco separado, por exemplo centric_test."
    )


def _create_test_database_if_missing() -> None:
    """Cria o banco de teste na primeira vez, para ninguém precisar criar na mão."""
    url = make_url(TEST_DATABASE_URL)

    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": url.database},
        ).scalar()

        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))

    admin_engine.dispose()


@pytest.fixture(scope="session")
def engine():
    _create_test_database_if_missing()

    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)

    yield engine

    engine.dispose()


@pytest.fixture()
def db_session(engine):
    """Cada teste começa com as tabelas vazias e um admin criado."""
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()

    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    session.add(
        User(
            name="Admin",
            email=ADMIN_EMAIL,
            password_hash="x",
            role=UserRole.ADMIN,
        )
    )
    session.commit()

    yield session

    session.close()


@pytest.fixture()
def current_user(db_session):
    return db_session.query(User).filter(User.email == ADMIN_EMAIL).first()


@pytest.fixture()
def client(db_session, current_user):

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[require_admin] = lambda: current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def unauthenticated_client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

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
            "title": "Culto de Quinta",
            "date": "2026-05-07",
            "description": "Culto de celebração",
        },
    )
    return response.json()["id"]
