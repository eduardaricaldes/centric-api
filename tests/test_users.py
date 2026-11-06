from app.core.dependencies import get_current_user, require_admin
from app.main import app
from app.models.ministry import Ministry
from app.models.ministry_member import MinistryMember
from app.models.roles import MinistryRole, UserRole
from app.models.user import User


def create_user(
    db_session, email: str, name: str | None = None, role: UserRole = UserRole.MEMBER
) -> User:
    user = User(
        name=name or email.split("@")[0],
        email=email,
        password_hash="x",
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_lista_usuarios_paginado(client, db_session):
    create_user(db_session, "ana@north.com", "Ana")
    create_user(db_session, "bruno@north.com", "Bruno")

    response = client.get("/users/", params={"page": 1, "limit": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["limit"] == 1
    assert body["total"] == 3  # inclui admin do fixture
    assert len(body["items"]) == 1


def test_lista_usuarios_nunca_expoe_password_hash(client, db_session):
    create_user(db_session, "ana@north.com", "Ana")

    response = client.get("/users/")
    for item in response.json()["items"]:
        assert "password_hash" not in item
        assert set(item.keys()) == {"id", "name", "email", "role", "prefers_chords"}


def test_lider_pode_buscar_usuarios_por_nome_ou_email(client, db_session):
    create_user(db_session, "vocal@north.com", "Vocalista")
    leader = create_user(db_session, "lider-b@north.com", "Lider", UserRole.LEADER)
    app.dependency_overrides[get_current_user] = lambda: leader

    response = client.get("/users/", params={"search": "vocal"})
    assert response.status_code == 200
    names = [item["email"] for item in response.json()["items"]]
    assert "vocal@north.com" in names

    response = client.get("/users/", params={"search": "vocal@north.com"})
    assert response.json()["total"] == 1


def test_membro_nao_lista_usuarios(client, db_session):
    member = create_user(db_session, "membro-b@north.com")
    app.dependency_overrides[get_current_user] = lambda: member

    response = client.get("/users/")
    assert response.status_code == 403


def add_to_new_ministry(db_session, user: User, role: MinistryRole) -> None:
    ministry = Ministry(name=f"Ministério de {user.email}")
    db_session.add(ministry)
    db_session.flush()
    db_session.add(MinistryMember(ministry_id=ministry.id, user_id=user.id, role=role))
    db_session.commit()


def test_admin_promove_a_admin(client, db_session):
    user = create_user(db_session, "promover@north.com")

    response = client.patch(f"/users/{user.id}/role", json={"role": "ADMIN"})
    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"


def test_papel_de_lider_exige_liderar_um_ministerio(client, db_session):
    user = create_user(db_session, "sem-ministerio@north.com")

    response = client.patch(f"/users/{user.id}/role", json={"role": "LEADER"})
    assert response.status_code == 409
    assert response.json()["detail"] == "User does not lead any ministry"

    db_session.refresh(user)
    assert user.role == UserRole.MEMBER


def test_admin_rebaixado_que_lidera_ministerio_volta_a_lider(client, db_session):
    other_admin = create_user(db_session, "admin-lider@north.com", role=UserRole.ADMIN)
    add_to_new_ministry(db_session, other_admin, MinistryRole.LEADER)

    response = client.patch(f"/users/{other_admin.id}/role", json={"role": "MEMBER"})

    assert response.status_code == 200
    assert response.json()["role"] == "LEADER"


def test_apenas_admin_muda_papel(client, db_session):
    user = create_user(db_session, "alvo-b@north.com")
    leader = create_user(db_session, "lider-b2@north.com", role=UserRole.LEADER)
    app.dependency_overrides.pop(require_admin)
    app.dependency_overrides[get_current_user] = lambda: leader

    response = client.patch(f"/users/{user.id}/role", json={"role": "MEMBER"})
    assert response.status_code == 403


def test_admin_nao_rebaixa_a_si_mesmo_mesmo_sendo_o_unico(client, current_user):
    # current_user é o único admin do banco de testes: some as duas travas ao mesmo tempo
    response = client.patch(f"/users/{current_user.id}/role", json={"role": "MEMBER"})
    assert response.status_code == 409


def test_admin_nao_rebaixa_a_si_mesmo_mesmo_com_outro_admin_disponivel(
    client, db_session, current_user
):
    create_user(db_session, "admin2-b@north.com", role=UserRole.ADMIN)

    response = client.patch(f"/users/{current_user.id}/role", json={"role": "MEMBER"})
    assert response.status_code == 409


def test_admin_pode_rebaixar_outro_admin_se_sobrar_pelo_menos_um(
    client, db_session, current_user
):
    other_admin = create_user(db_session, "admin2-b@north.com", role=UserRole.ADMIN)

    response = client.patch(f"/users/{other_admin.id}/role", json={"role": "MEMBER"})
    assert response.status_code == 200
    assert response.json()["role"] == "MEMBER"


def test_usuario_inexistente_da_404(client):
    response = client.patch("/users/999/role", json={"role": "LEADER"})
    assert response.status_code == 404
