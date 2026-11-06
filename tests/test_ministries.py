from app.core.dependencies import get_current_user, require_admin
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
        assert set(item.keys()) == {"id", "name", "description"}


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


# ---------------------------------------------------------------------------
# A1. Criar e renomear ministério
# ---------------------------------------------------------------------------


def test_admin_cria_ministerio(client):
    response = client.post("/ministries/", json={"name": "Recepção"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Recepção"
    assert body["description"] is None


def test_criar_ministerio_com_nome_repetido_da_409(client, db_session):
    db_session.add(Ministry(name="Louvor"))
    db_session.commit()

    response = client.post("/ministries/", json={"name": "Louvor"})
    assert response.status_code == 409


def test_criar_ministerio_nome_vazio_da_422(client):
    response = client.post("/ministries/", json={"name": ""})
    assert response.status_code == 422


def test_apenas_admin_cria_ministerio(client, db_session):
    leader = create_user(db_session, "lider-a1@north.com", UserRole.LEADER)
    app.dependency_overrides.pop(require_admin)
    app.dependency_overrides[get_current_user] = lambda: leader

    response = client.post("/ministries/", json={"name": "Mídia"})
    assert response.status_code == 403


def test_admin_renomeia_ministerio(client, db_session):
    ministry = Ministry(name="Louvor", description="antigo")
    db_session.add(ministry)
    db_session.commit()

    response = client.patch(
        f"/ministries/{ministry.id}",
        json={"name": "Louvor e Adoração", "description": "novo"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Louvor e Adoração"
    assert body["description"] == "novo"


def test_renomear_ministerio_para_nome_existente_da_409(client, db_session):
    db_session.add_all([Ministry(name="Louvor"), Ministry(name="Mídia")])
    db_session.commit()
    midia = db_session.query(Ministry).filter(Ministry.name == "Mídia").first()

    response = client.patch(f"/ministries/{midia.id}", json={"name": "Louvor"})
    assert response.status_code == 409


def test_renomear_ministerio_inexistente_da_404(client):
    response = client.patch("/ministries/999", json={"name": "Novo"})
    assert response.status_code == 404


def test_apenas_admin_renomeia_ministerio(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()

    member = create_user(db_session, "membro-a1@north.com")
    app.dependency_overrides.pop(require_admin)
    app.dependency_overrides[get_current_user] = lambda: member

    response = client.patch(f"/ministries/{ministry.id}", json={"name": "Novo nome"})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# A2. Membros
# ---------------------------------------------------------------------------


def test_admin_adiciona_membro(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    user = create_user(db_session, "novo-membro@north.com")

    response = client.post(
        f"/ministries/{ministry.id}/members",
        json={"user_id": user.id, "instrument": "Baixo"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "MEMBER"
    assert body["instrument"] == "Baixo"


def test_admin_adiciona_membro_como_lider_promove_papel_global(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    user = create_user(db_session, "futuro-lider@north.com")

    response = client.post(
        f"/ministries/{ministry.id}/members",
        json={"user_id": user.id, "role": "LEADER"},
    )
    assert response.status_code == 201

    db_session.refresh(user)
    assert user.role == UserRole.LEADER


def test_membro_duplicado_da_409(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    user = create_user(db_session, "duplicado@north.com")
    db_session.add(MinistryMember(ministry_id=ministry.id, user_id=user.id))
    db_session.commit()

    response = client.post(
        f"/ministries/{ministry.id}/members",
        json={"user_id": user.id},
    )
    assert response.status_code == 409


def test_adicionar_membro_usuario_inexistente_da_404(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()

    response = client.post(
        f"/ministries/{ministry.id}/members",
        json={"user_id": 999},
    )
    assert response.status_code == 404


def test_adicionar_membro_ministerio_inexistente_da_404(client, db_session):
    user = create_user(db_session, "sem-ministerio@north.com")

    response = client.post(
        "/ministries/999/members",
        json={"user_id": user.id},
    )
    assert response.status_code == 404


def test_lider_nao_pode_criar_outro_lider(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()

    leader = create_user(db_session, "lider-a2@north.com", UserRole.LEADER)
    db_session.add(
        MinistryMember(
            ministry_id=ministry.id, user_id=leader.id, role=MinistryRole.LEADER
        )
    )
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: leader

    target = create_user(db_session, "alvo@north.com")
    response = client.post(
        f"/ministries/{ministry.id}/members",
        json={"user_id": target.id, "role": "LEADER"},
    )
    assert response.status_code == 403


def test_lider_so_adiciona_membro_no_proprio_ministerio(client, db_session):
    own = Ministry(name="Louvor")
    other = Ministry(name="Mídia")
    db_session.add_all([own, other])
    db_session.commit()

    leader = create_user(db_session, "lider-a2b@north.com", UserRole.LEADER)
    db_session.add(
        MinistryMember(ministry_id=own.id, user_id=leader.id, role=MinistryRole.LEADER)
    )
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: leader

    target = create_user(db_session, "alvo2@north.com")
    response = client.post(
        f"/ministries/{other.id}/members",
        json={"user_id": target.id},
    )
    assert response.status_code == 403


def test_atualiza_membro_instrumento_e_papel(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    user = create_user(db_session, "editar@north.com")
    db_session.add(MinistryMember(ministry_id=ministry.id, user_id=user.id))
    db_session.commit()

    response = client.patch(
        f"/ministries/{ministry.id}/members/{user.id}",
        json={"instrument": "Bateria"},
    )
    assert response.status_code == 200
    assert response.json()["instrument"] == "Bateria"


def test_atualizar_membro_inexistente_da_404(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()

    response = client.patch(
        f"/ministries/{ministry.id}/members/999",
        json={"instrument": "Bateria"},
    )
    assert response.status_code == 404


def test_remove_membro_do_ministerio(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    user = create_user(db_session, "sair@north.com")
    db_session.add(MinistryMember(ministry_id=ministry.id, user_id=user.id))
    db_session.commit()

    response = client.delete(f"/ministries/{ministry.id}/members/{user.id}")
    assert response.status_code == 204
    assert (
        db_session.query(MinistryMember)
        .filter(MinistryMember.ministry_id == ministry.id, MinistryMember.user_id == user.id)
        .first()
        is None
    )


def test_remover_membro_inexistente_da_404(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()

    response = client.delete(f"/ministries/{ministry.id}/members/999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# A3. Regra de ouro: papel global e ministério escritos juntos
# ---------------------------------------------------------------------------


def test_tirar_lideranca_do_unico_ministerio_rebaixa_papel_global(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    leader = create_user(db_session, "sozinho@north.com", UserRole.LEADER)
    db_session.add(
        MinistryMember(ministry_id=ministry.id, user_id=leader.id, role=MinistryRole.LEADER)
    )
    db_session.commit()

    response = client.patch(
        f"/ministries/{ministry.id}/members/{leader.id}",
        json={"role": "MEMBER"},
    )
    assert response.status_code == 200

    db_session.refresh(leader)
    assert leader.role == UserRole.MEMBER


def test_lider_de_dois_ministerios_que_perde_um_continua_lider(client, db_session):
    m1 = Ministry(name="Louvor")
    m2 = Ministry(name="Mídia")
    db_session.add_all([m1, m2])
    db_session.commit()
    leader = create_user(db_session, "dois-ministerios@north.com", UserRole.LEADER)
    db_session.add_all([
        MinistryMember(ministry_id=m1.id, user_id=leader.id, role=MinistryRole.LEADER),
        MinistryMember(ministry_id=m2.id, user_id=leader.id, role=MinistryRole.LEADER),
    ])
    db_session.commit()

    response = client.delete(f"/ministries/{m1.id}/members/{leader.id}")
    assert response.status_code == 204

    db_session.refresh(leader)
    assert leader.role == UserRole.LEADER


def test_admin_promovido_a_lider_de_ministerio_continua_admin(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    admin2 = create_user(db_session, "admin2@north.com", UserRole.ADMIN)

    response = client.post(
        f"/ministries/{ministry.id}/members",
        json={"user_id": admin2.id, "role": "LEADER"},
    )
    assert response.status_code == 201

    db_session.refresh(admin2)
    assert admin2.role == UserRole.ADMIN
