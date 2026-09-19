from app.core.dependencies import get_current_user
from app.main import app
from app.models.ministry import Ministry
from app.models.ministry_member import MinistryMember
from app.models.roles import MinistryRole, UserRole
from app.models.user import User


def create_user(db_session, email: str, role: UserRole = UserRole.MEMBER) -> User:
    user = User(name=email.split("@")[0], email=email, password_hash="x", role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_lista_ministerios(client, db_session):
    louvor = Ministry(name="Louvor")
    midia = Ministry(name="Mídia")
    db_session.add_all([louvor, midia])
    db_session.commit()

    response = client.get("/ministries/")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    names = [item["name"] for item in body["items"]]
    assert "Louvor" in names
    assert "Mídia" in names
    for item in body["items"]:
        assert set(item.keys()) == {"id", "name"}


def test_lider_lista_ministerios(client, db_session):
    db_session.add(Ministry(name="Louvor"))
    db_session.commit()

    lider = create_user(db_session, "lider@north.com", UserRole.LEADER)
    app.dependency_overrides[get_current_user] = lambda: lider

    response = client.get("/ministries/")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_membro_nao_lista_ministerios(client, db_session):
    member = create_user(db_session, "member@north.com")
    app.dependency_overrides[get_current_user] = lambda: member

    response = client.get("/ministries/")
    assert response.status_code == 403


def test_lista_membros_do_ministerio(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()

    user1 = create_user(db_session, "vocal@north.com")
    user2 = create_user(db_session, "teclado@north.com")
    db_session.add_all([
        MinistryMember(
            ministry_id=ministry.id, user_id=user1.id,
            role=MinistryRole.LEADER, instrument="Vocal",
        ),
        MinistryMember(
            ministry_id=ministry.id, user_id=user2.id,
            role=MinistryRole.MEMBER, instrument="Teclado",
        ),
    ])
    db_session.commit()

    response = client.get(f"/ministries/{ministry.id}/members")
    assert response.status_code == 200
    members = response.json()
    assert len(members) == 2

    # check mínimo exposto: sem e-mail
    for m in members:
        assert "email" not in m
        assert "user_id" in m
        assert "name" in m
        assert "role" in m

    leader = next(m for m in members if m["role"] == "LEADER")
    assert leader["name"] == "vocal"
    assert leader["instrument"] == "Vocal"


def test_ministerio_inexistente_retorna_404(client):
    response = client.get("/ministries/999/members")
    assert response.status_code == 404
