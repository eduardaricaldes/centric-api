from datetime import date, timedelta

import pytest
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.api import live
from app.core.dependencies import get_current_user
from app.main import app
from app.models.roles import UserRole
from app.models.user import User


@pytest.fixture()
def event_link(client):
    event = client.post(
        "/events/",
        json={
            "title": "Culto",
            "date": (date.today() + timedelta(days=1)).isoformat(),
            "time": "19:00:00",
            "type": "CULTO",
        },
    ).json()
    token = client.post("/share-links/", json={"event_id": event["id"]}).json()["token"]
    return event["id"], token


@pytest.fixture()
def ws_session(engine):
    original = live.session_factory
    live.session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    yield
    live.session_factory = original


def test_celular_comeca_no_logo(client, unauthenticated_client, event_link):
    _, token = event_link
    response = unauthenticated_client.get(f"/public/live/{token}")
    assert response.status_code == 200
    assert response.json()["mode"] == "logo"
    assert response.json()["version"] == 0


def test_operador_manda_slide_e_celular_le(client, unauthenticated_client, event_link):
    event_id, token = event_link
    response = client.put(
        f"/events/{event_id}/live",
        json={"mode": "slide", "song_index": 0, "slide_index": 2, "song_title": "Santo", "lines": ["Santo, santo", "Digno"]},
    )
    assert response.status_code == 200

    body = unauthenticated_client.get(f"/public/live/{token}").json()
    assert body["mode"] == "slide"
    assert body["lines"] == ["Santo, santo", "Digno"]
    assert body["slide_index"] == 2
    assert body["version"] == 1

    client.put(f"/events/{event_id}/live", json={"mode": "black"})
    body = unauthenticated_client.get(f"/public/live/{token}").json()
    assert body["mode"] == "black"
    assert body["lines"] == []
    assert body["version"] == 2


def test_membro_nao_controla_o_telao(client, db_session, event_link):
    event_id, _ = event_link
    member = User(name="M", email="m@example.com", password_hash="x", role=UserRole.MEMBER)
    db_session.add(member)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: member

    response = client.put(f"/events/{event_id}/live", json={"mode": "logo"})
    assert response.status_code == 403


def test_link_de_musica_nao_serve_para_ao_vivo(client, unauthenticated_client):
    song = client.post("/songs/", json={"title": "T", "lyrics": "L"}).json()
    token = client.post("/share-links/", json={"song_id": song["id"]}).json()["token"]
    assert unauthenticated_client.get(f"/public/live/{token}").status_code == 404


def test_websocket_recebe_estado_e_atualizacoes(client, event_link, ws_session):
    event_id, token = event_link
    with client.websocket_connect(f"/public/live/{token}/ws") as socket:
        assert socket.receive_json()["mode"] == "logo"
        client.put(f"/events/{event_id}/live", json={"mode": "slide", "lines": ["Aleluia"]})
        update = socket.receive_json()
        assert update["mode"] == "slide"
        assert update["lines"] == ["Aleluia"]


def test_websocket_com_token_invalido_fecha(client, ws_session):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/public/live/token-que-nao-existe-123/ws") as socket:
            socket.receive_json()
