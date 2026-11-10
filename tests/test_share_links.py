import pytest

from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.main import app
from app.models.ministry import Ministry
from app.models.ministry_member import MinistryMember
from app.models.roles import MinistryRole, UserRole
from app.models.share_link import ShareLink
from app.models.user import User

SONG_KEYS = {"title", "artist", "tone", "lyrics", "chordpro"}


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


def act_as(user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def create_event(client, **overrides) -> dict:
    payload = {
        "title": "Culto de domingo",
        "date": "2026-10-04",
        "time": "19:00:00",
        "type": "CULTO",
    }
    payload.update(overrides)
    response = client.post("/events/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_song(client, **overrides) -> dict:
    payload = {
        "title": "Ousado Amor",
        "artist": "Isaias Saad",
        "tone": "G",
        "lyrics": "placeholder",
        "chordpro": "[G]Ousado [D]amor",
        "category": "Adoração",
        "duration_min": 5,
    }
    payload.update(overrides)
    response = client.post("/songs/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture()
def worship_event(client, db_session):
    """Culto com repertório de duas músicas e um voluntário escalado."""
    event = create_event(client)
    first = create_song(client, title="Primeira")
    second = create_song(client, title="Segunda", chordpro=None, lyrics="só letra")

    playlist = client.post(
        "/playlist/",
        json={"title": "Repertório", "date": "2026-10-04", "event_id": event["id"]},
    ).json()
    for song in [second, first]:
        client.post(f"/playlist/{playlist['id']}/songs/", json={"song_id": song["id"]})

    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    volunteer = create_user(db_session, "voluntaria@north.com")
    response = client.post(
        f"/events/{event['id']}/assignments",
        json={"user_id": volunteer.id, "ministry_id": ministry.id, "function": "Vocal"},
    )
    assert response.status_code == 201, response.text

    return {"event": event, "ministry": ministry, "songs": [second, first]}


def lead(db_session, user: User, ministry: Ministry) -> None:
    db_session.add(
        MinistryMember(ministry_id=ministry.id, user_id=user.id, role=MinistryRole.LEADER)
    )
    db_session.commit()


# Criar


def test_admin_cria_link_de_musica_com_token_longo(client):
    song = create_song(client)

    response = client.post("/share-links/", json={"song_id": song["id"]})

    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "SONG"
    assert body["song_id"] == song["id"]
    assert body["event_id"] is None
    assert len(body["token"]) >= 40


def test_criar_de_novo_devolve_o_link_ativo(client):
    song = create_song(client)
    first = client.post("/share-links/", json={"song_id": song["id"]})

    again = client.post("/share-links/", json={"song_id": song["id"]})

    assert again.status_code == 200
    assert again.json()["token"] == first.json()["token"]


def test_exige_exatamente_um_alvo(client):
    song = create_song(client)
    event = create_event(client)

    assert client.post("/share-links/", json={}).status_code == 422
    both = client.post(
        "/share-links/", json={"song_id": song["id"], "event_id": event["id"]}
    )
    assert both.status_code == 422


def test_alvo_inexistente_da_404(client):
    assert client.post("/share-links/", json={"song_id": 999}).status_code == 404
    assert client.post("/share-links/", json={"event_id": 999}).status_code == 404


def test_member_nao_cria_link(client, db_session):
    song = create_song(client)
    event = create_event(client)
    act_as(create_user(db_session, "membro@north.com"))

    assert client.post("/share-links/", json={"song_id": song["id"]}).status_code == 403
    assert client.post("/share-links/", json={"event_id": event["id"]}).status_code == 403


def test_lider_nao_compartilha_musica_avulsa(client, db_session):
    song = create_song(client)
    act_as(create_user(db_session, "lider@north.com", UserRole.LEADER))

    assert client.post("/share-links/", json={"song_id": song["id"]}).status_code == 403


def test_lider_compartilha_evento_do_ministerio_que_lidera(
    client, db_session, worship_event
):
    leader = create_user(db_session, "lider@north.com", UserRole.LEADER)
    lead(db_session, leader, worship_event["ministry"])
    act_as(leader)

    response = client.post(
        "/share-links/", json={"event_id": worship_event["event"]["id"]}
    )

    assert response.status_code == 201
    assert response.json()["kind"] == "EVENT"


def test_lider_compartilha_evento_que_criou(client, db_session):
    leader = create_user(db_session, "lider@north.com", UserRole.LEADER)
    act_as(leader)
    event = create_event(client)

    assert client.post("/share-links/", json={"event_id": event["id"]}).status_code == 201


def test_lider_de_outro_ministerio_nao_compartilha_evento(
    client, db_session, worship_event
):
    other = Ministry(name="Mídia")
    db_session.add(other)
    db_session.commit()
    leader = create_user(db_session, "midia@north.com", UserRole.LEADER)
    lead(db_session, leader, other)
    act_as(leader)

    response = client.post(
        "/share-links/", json={"event_id": worship_event["event"]["id"]}
    )

    assert response.status_code == 403


# Listar e revogar


def test_lista_so_links_ativos_do_alvo(client):
    song = create_song(client)
    other = create_song(client, title="Outra")
    link = client.post("/share-links/", json={"song_id": song["id"]}).json()
    client.post("/share-links/", json={"song_id": other["id"]})

    response = client.get("/share-links/", params={"song_id": song["id"]})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [link["id"]]

    client.delete(f"/share-links/{link['id']}")
    response = client.get("/share-links/", params={"song_id": song["id"]})
    assert response.json() == {"total": 0, "items": []}


def test_listar_exige_um_alvo(client):
    assert client.get("/share-links/").status_code == 422


def test_revogar_derruba_o_link_e_permite_um_novo(client, unauthenticated_client):
    song = create_song(client)
    link = client.post("/share-links/", json={"song_id": song["id"]}).json()

    response = client.delete(f"/share-links/{link['id']}")

    assert response.status_code == 204
    assert unauthenticated_client.get(f"/public/share/{link['token']}").status_code == 404
    assert client.delete(f"/share-links/{link['id']}").status_code == 404

    new = client.post("/share-links/", json={"song_id": song["id"]})
    assert new.status_code == 201
    assert new.json()["token"] != link["token"]


def test_lider_revoga_link_do_evento_do_ministerio(client, db_session, worship_event):
    link = client.post(
        "/share-links/", json={"event_id": worship_event["event"]["id"]}
    ).json()
    leader = create_user(db_session, "lider@north.com", UserRole.LEADER)
    lead(db_session, leader, worship_event["ministry"])
    act_as(leader)

    assert client.delete(f"/share-links/{link['id']}").status_code == 204


def test_member_e_lider_de_fora_nao_revogam(client, db_session, worship_event):
    song = create_song(client, title="Avulsa")
    song_link = client.post("/share-links/", json={"song_id": song["id"]}).json()
    event_link = client.post(
        "/share-links/", json={"event_id": worship_event["event"]["id"]}
    ).json()

    act_as(create_user(db_session, "membro@north.com"))
    assert client.delete(f"/share-links/{event_link['id']}").status_code == 403

    act_as(create_user(db_session, "fora@north.com", UserRole.LEADER))
    assert client.delete(f"/share-links/{event_link['id']}").status_code == 403
    assert client.delete(f"/share-links/{song_link['id']}").status_code == 403

    assert db_session.query(ShareLink).filter(ShareLink.revoked_at.isnot(None)).count() == 0


# Acesso público


def test_publico_le_musica_sem_login(client, unauthenticated_client):
    song = create_song(client)
    token = client.post("/share-links/", json={"song_id": song["id"]}).json()["token"]

    response = unauthenticated_client.get(f"/public/share/{token}")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "noindex" in response.headers["x-robots-tag"]
    assert response.json() == {
        "kind": "song",
        "song": {
            "title": "Ousado Amor",
            "artist": "Isaias Saad",
            "tone": "G",
            "lyrics": "Ousado amor",
            "chordpro": "[G]Ousado [D]amor",
        },
    }


def test_publico_le_repertorio_do_evento_na_ordem(
    client, unauthenticated_client, worship_event
):
    token = client.post(
        "/share-links/", json={"event_id": worship_event["event"]["id"]}
    ).json()["token"]

    response = unauthenticated_client.get(f"/public/share/{token}")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "event"
    assert body["title"] == "Culto de domingo"
    assert body["date"] == "2026-10-04"
    assert [song["title"] for song in body["songs"]] == ["Segunda", "Primeira"]
    assert body["songs"][0]["chordpro"] is None
    assert body["songs"][0]["lyrics"] == "só letra"


def test_evento_sem_repertorio_devolve_lista_vazia(client, unauthenticated_client):
    event = create_event(client)
    token = client.post("/share-links/", json={"event_id": event["id"]}).json()["token"]

    response = unauthenticated_client.get(f"/public/share/{token}")

    assert response.status_code == 200
    assert response.json()["songs"] == []


def test_token_inexistente_da_404(unauthenticated_client):
    response = unauthenticated_client.get("/public/share/" + "x" * 43)
    assert response.status_code == 404


def test_apagar_musica_apaga_o_link(client, unauthenticated_client):
    song = create_song(client)
    token = client.post("/share-links/", json={"song_id": song["id"]}).json()["token"]

    client.delete(f"/songs/{song['id']}")

    assert unauthenticated_client.get(f"/public/share/{token}").status_code == 404


def test_rotas_de_gestao_exigem_login(unauthenticated_client):
    assert unauthenticated_client.post("/share-links/", json={"song_id": 1}).status_code == 401
    assert unauthenticated_client.get("/share-links/", params={"song_id": 1}).status_code == 401
    assert unauthenticated_client.delete("/share-links/1").status_code == 401


# Vazamento de campos


def test_evento_publico_nao_vaza_pessoas_escalas_nem_emails(
    client, unauthenticated_client, db_session, worship_event
):
    event_id = worship_event["event"]["id"]
    preacher = create_user(db_session, "pregador@north.com")
    preaching = client.put(
        f"/events/{event_id}/preaching",
        json={"preacher_id": preacher.id, "theme": "Tema secreto"},
    )
    assert preaching.status_code == 200, preaching.text
    token = client.post("/share-links/", json={"event_id": event_id}).json()["token"]

    response = unauthenticated_client.get(f"/public/share/{token}")

    body = response.json()
    assert set(body) == {"kind", "title", "date", "songs"}
    for song in body["songs"]:
        assert set(song) == SONG_KEYS
    raw = response.text
    for secret in [
        "@north.com",
        "@comunidadenorth.com",
        "voluntaria",
        "pregador",
        "Vocal",
        "Louvor",
        "Tema secreto",
        "created_by",
        "id",
    ]:
        assert secret not in raw, secret


def test_musica_publica_nao_vaza_ids_categoria_nem_datas(client, unauthenticated_client):
    song = create_song(client)
    token = client.post("/share-links/", json={"song_id": song["id"]}).json()["token"]

    body = unauthenticated_client.get(f"/public/share/{token}").json()

    assert set(body) == {"kind", "song"}
    assert set(body["song"]) == SONG_KEYS
    assert token not in str(body)


# Rate limit


@pytest.fixture()
def rate_limit_on():
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


def test_rota_publica_bloqueia_apos_60_leituras_por_minuto(
    unauthenticated_client, rate_limit_on
):
    for _ in range(60):
        assert unauthenticated_client.get("/public/share/" + "x" * 43).status_code == 404

    assert unauthenticated_client.get("/public/share/" + "x" * 43).status_code == 429
