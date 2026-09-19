from app.core.dependencies import get_current_user
from app.main import app
from app.models.ministry import Ministry
from app.models.ministry_member import MinistryMember
from app.models.roles import MinistryRole, UserRole
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


def create_event(client) -> int:
    response = client.post(
        "/events/",
        json={
            "title": "Culto",
            "date": "2026-10-04",
            "time": "19:00:00",
            "type": "CULTO",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_apenas_usuario_escalado_responde_e_ve_a_propria_escala(
    client,
    db_session,
):
    event_id = create_event(client)
    assigned = create_user(db_session, "assigned@example.com")
    outsider = create_user(db_session, "outsider@example.com")
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()

    response = client.post(
        f"/events/{event_id}/assignments",
        json={
            "user_id": assigned.id,
            "ministry_id": ministry.id,
            "function": "Guitarra",
        },
    )
    assignment_id = response.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: outsider
    response = client.post(
        f"/assignments/{assignment_id}/respond",
        json={"status": "CONFIRMADO"},
    )
    assert response.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: assigned
    response = client.post(
        f"/assignments/{assignment_id}/respond",
        json={"status": "CONFIRMADO"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "CONFIRMADO"
    assert response.json()["responded_at"] is not None

    response = client.get("/me/assignments")
    assert response.status_code == 200
    assert response.json()[0]["event_title"] == "Culto"
    assert response.json()[0]["event_date"] == "2026-10-04"


def test_lider_so_altera_escalas_do_ministerio_que_lidera(client, db_session):
    event_id = create_event(client)
    leader = create_user(db_session, "scale-leader@example.com", UserRole.LEADER)
    volunteer = create_user(db_session, "scale-member@example.com")
    own_ministry = Ministry(name="Louvor")
    other_ministry = Ministry(name="Mídia")
    db_session.add_all([own_ministry, other_ministry])
    db_session.flush()
    db_session.add(
        MinistryMember(
            ministry_id=own_ministry.id,
            user_id=leader.id,
            role=MinistryRole.LEADER,
        )
    )
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: leader
    response = client.post(
        f"/events/{event_id}/assignments",
        json={
            "user_id": volunteer.id,
            "ministry_id": own_ministry.id,
            "function": "Bateria",
        },
    )
    assert response.status_code == 201
    assignment_id = response.json()["id"]

    response = client.post(
        f"/events/{event_id}/assignments",
        json={
            "user_id": volunteer.id,
            "ministry_id": other_ministry.id,
            "function": "Projeção",
        },
    )
    assert response.status_code == 403

    response = client.patch(
        f"/assignments/{assignment_id}",
        json={"ministry_id": other_ministry.id},
    )
    assert response.status_code == 403


def test_lider_monta_playlist_do_evento_que_criou(client, db_session):
    leader = create_user(db_session, "playlist-leader@example.com", UserRole.LEADER)
    app.dependency_overrides[get_current_user] = lambda: leader
    event_id = create_event(client)

    response = client.post(
        "/playlist/",
        json={
            "title": "Playlist do líder",
            "date": "2026-10-04",
            "event_id": event_id,
        },
    )
    assert response.status_code == 201
    assert response.json()["created_by"] == leader.id
    assert response.json()["event_id"] == event_id

    response = client.post(
        "/playlist/",
        json={"title": "Sem escopo", "date": "2026-10-05"},
    )
    assert response.status_code == 403
