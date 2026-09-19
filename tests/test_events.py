from app.core.dependencies import get_current_user
from app.main import app
from app.models.event import Event
from app.models.ministry import Ministry
from app.models.playlist import Playlist
from app.models.roles import UserRole
from app.models.user import User


def create_user(db_session, email: str, role: UserRole = UserRole.MEMBER) -> User:
    user = User(
        name=email.split("@", maxsplit=1)[0],
        email=email,
        password_hash="x",
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_event(client, **overrides) -> dict:
    payload = {
        "title": "Culto de domingo",
        "date": "2026-10-04",
        "time": "19:00:00",
        "type": "CULTO_DOMINGO",
    }
    payload.update(overrides)
    response = client.post("/events/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_cria_lista_filtra_e_atualiza_eventos(client):
    first = create_event(client)
    create_event(
        client,
        title="Ensaio geral",
        date="2026-10-02",
        type="ENSAIO",
        status="PUBLICADO",
    )

    response = client.get(
        "/events/",
        params={
            "from": "2026-10-01",
            "to": "2026-10-03",
            "type": "ENSAIO",
            "status": "PUBLICADO",
        },
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["title"] == "Ensaio geral"

    response = client.put(
        f"/events/{first['id']}",
        json={"status": "PUBLICADO"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PUBLICADO"


def test_rejeita_intervalo_de_datas_invertido(client):
    response = client.get(
        "/events/",
        params={"from": "2026-10-05", "to": "2026-10-01"},
    )
    assert response.status_code == 400


def test_member_nao_cria_evento(client, db_session):
    member = create_user(db_session, "member-event@example.com")
    app.dependency_overrides[get_current_user] = lambda: member

    response = client.post(
        "/events/",
        json={
            "title": "Sem permissão",
            "date": "2026-10-04",
            "time": "19:00:00",
            "type": "EVENTO",
        },
    )

    assert response.status_code == 403


def test_lider_gerencia_evento_proprio_mas_nao_o_de_outro_lider(
    client,
    db_session,
):
    leader = create_user(db_session, "leader-one@example.com", UserRole.LEADER)
    other_leader = create_user(db_session, "leader-two@example.com", UserRole.LEADER)

    app.dependency_overrides[get_current_user] = lambda: leader
    own_event = create_event(client, title="Evento do primeiro líder")

    app.dependency_overrides[get_current_user] = lambda: other_leader
    response = client.put(
        f"/events/{own_event['id']}",
        json={"title": "Tentativa indevida"},
    )

    assert response.status_code == 403


def test_detalhe_reune_escala_pregacao_playlist_e_aviso_de_conflito(
    client,
    db_session,
):
    event = create_event(client)
    volunteer = create_user(db_session, "volunteer@example.com")
    preacher = create_user(db_session, "preacher@example.com")
    worship = Ministry(name="Louvor")
    media = Ministry(name="Mídia")
    db_session.add_all([worship, media])
    db_session.commit()

    for ministry, function in [(worship, "Vocal"), (media, "Projeção")]:
        response = client.post(
            f"/events/{event['id']}/assignments",
            json={
                "user_id": volunteer.id,
                "ministry_id": ministry.id,
                "function": function,
            },
        )
        assert response.status_code == 201

    response = client.put(
        f"/events/{event['id']}/preaching",
        json={
            "preacher_id": preacher.id,
            "theme": "Graça",
            "bible_reference": "Efésios 2:8",
        },
    )
    assert response.status_code == 200

    playlist = client.post(
        "/playlist/",
        json={
            "title": "Repertório de domingo",
            "date": "2026-10-04",
            "event_id": event["id"],
        },
    )
    assert playlist.status_code == 201

    song = client.post(
        "/songs/",
        json={"title": "Canção", "lyrics": "Uma letra", "chordpro": "[C]Uma letra"},
    )
    client.post(
        f"/playlist/{playlist.json()['id']}/songs/",
        json={"song_id": song.json()["id"]},
    )

    response = client.get(f"/events/{event['id']}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["assignments"]) == 2
    assert body["preaching"]["theme"] == "Graça"
    assert body["playlist"]["songs"][0]["song"]["lyrics"] == "Uma letra"
    assert body["warnings"] == [
        {
            "code": "USER_MULTIPLE_MINISTRIES",
            "message": "User is assigned to multiple ministries in this event",
            "user_id": volunteer.id,
            "ministry_ids": [worship.id, media.id],
        }
    ]


def test_lider_monta_repertorio_de_culto_criado_pelo_admin(client, db_session):
    event = create_event(client)

    lider = create_user(db_session, "louvor@north.com", UserRole.LEADER)
    app.dependency_overrides[get_current_user] = lambda: lider

    r = client.post(
        "/playlist/",
        json={"title": "Repertório", "date": "2026-10-04", "event_id": event["id"]},
    )
    assert r.status_code == 201


def test_lider_nao_pode_editar_nem_apagar_evento_de_outro(client, db_session):
    event = create_event(client)

    outro_lider = create_user(db_session, "outro@north.com", UserRole.LEADER)
    app.dependency_overrides[get_current_user] = lambda: outro_lider

    r = client.put(f"/events/{event['id']}", json={"title": "Tentativa"})
    assert r.status_code == 403

    r = client.delete(f"/events/{event['id']}")
    assert r.status_code == 403


def test_excluir_evento_preserva_playlist_desvinculada(client, db_session):
    event = create_event(client)
    playlist_response = client.post(
        "/playlist/",
        json={
            "title": "Playlist preservada",
            "date": "2026-10-04",
            "event_id": event["id"],
        },
    )
    playlist_id = playlist_response.json()["id"]

    assert client.delete(f"/events/{event['id']}").status_code == 204

    db_session.expire_all()
    playlist = db_session.query(Playlist).filter(Playlist.id == playlist_id).one()
    assert playlist.event_id is None
    assert db_session.query(Event).filter(Event.id == event["id"]).first() is None
