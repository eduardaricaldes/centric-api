from datetime import timedelta

from app.core.dependencies import get_current_user
from app.main import app
from app.models.invite import Invite, InviteKind
from app.models.ministry import Ministry
from app.models.ministry_member import MinistryMember
from app.models.roles import MinistryRole, UserRole
from app.models.user import User
from app.services.invites import hash_token, utcnow


def create_user(db_session, email: str, role: UserRole = UserRole.MEMBER) -> User:
    user = User(name=email.split("@")[0], email=email, password_hash="x", role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_leader(db_session, email: str, ministry: Ministry) -> User:
    leader = create_user(db_session, email, UserRole.LEADER)
    db_session.add(
        MinistryMember(ministry_id=ministry.id, user_id=leader.id, role=MinistryRole.LEADER)
    )
    db_session.commit()
    return leader


def raw_invite(
    db_session,
    token: str,
    kind: InviteKind = InviteKind.INVITE,
    created_by: int = 1,
    email: str | None = None,
    role: UserRole | None = UserRole.MEMBER,
    ministry_id: int | None = None,
    ministry_role: MinistryRole | None = None,
    expires_delta: timedelta = timedelta(days=7),
    used_at=None,
) -> Invite:
    invite = Invite(
        kind=kind,
        token_hash=hash_token(token),
        email=email,
        role=role,
        ministry_id=ministry_id,
        ministry_role=ministry_role,
        created_by=created_by,
        expires_at=utcnow() + expires_delta,
        used_at=used_at,
    )
    db_session.add(invite)
    db_session.commit()
    db_session.refresh(invite)
    return invite


# ---------------------------------------------------------------------------
# C2. Criar, listar e cancelar convites
# ---------------------------------------------------------------------------


def test_admin_cria_convite_para_qualquer_papel_e_ministerio(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()

    response = client.post(
        "/invites/",
        json={"role": "LEADER", "ministry_id": ministry.id, "ministry_role": "LEADER"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "token" in body and body["token"]
    assert body["role"] == "LEADER"


def test_lider_cria_convite_de_membro_para_seu_ministerio(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    leader = make_leader(db_session, "lider-c@north.com", ministry)
    app.dependency_overrides[get_current_user] = lambda: leader

    response = client.post(
        "/invites/",
        json={"ministry_id": ministry.id},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "MEMBER"


def test_lider_nao_pode_convidar_como_lider(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    leader = make_leader(db_session, "lider-c2@north.com", ministry)
    app.dependency_overrides[get_current_user] = lambda: leader

    response = client.post(
        "/invites/",
        json={"role": "LEADER", "ministry_id": ministry.id},
    )
    assert response.status_code == 403


def test_lider_nao_pode_convidar_como_admin(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    leader = make_leader(db_session, "lider-c3@north.com", ministry)
    app.dependency_overrides[get_current_user] = lambda: leader

    response = client.post(
        "/invites/",
        json={"role": "ADMIN", "ministry_id": ministry.id},
    )
    assert response.status_code == 403


def test_lider_nao_pode_convidar_para_ministerio_que_nao_lidera(client, db_session):
    own = Ministry(name="Louvor")
    other = Ministry(name="Mídia")
    db_session.add_all([own, other])
    db_session.commit()
    leader = make_leader(db_session, "lider-c4@north.com", own)
    app.dependency_overrides[get_current_user] = lambda: leader

    response = client.post(
        "/invites/",
        json={"ministry_id": other.id},
    )
    assert response.status_code == 403


def test_convidar_email_que_ja_tem_conta_da_409(client, db_session):
    create_user(db_session, "jatemconta@north.com")

    response = client.post(
        "/invites/",
        json={"email": "jatemconta@north.com"},
    )
    assert response.status_code == 409


def test_admin_ve_todos_convites_lider_ve_so_os_dele(client, db_session, current_user):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    leader = make_leader(db_session, "lider-c5@north.com", ministry)

    client.post("/invites/", json={"email": "convite-admin@north.com"})

    app.dependency_overrides[get_current_user] = lambda: leader
    client.post("/invites/", json={"ministry_id": ministry.id, "email": "convite-lider@north.com"})

    response = client.get("/invites/")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["email"] == "convite-lider@north.com"

    app.dependency_overrides[get_current_user] = lambda: current_user
    admin_response = client.get("/invites/")
    assert admin_response.json()["total"] == 2


def test_convite_expirado_nao_aparece_na_listagem(client, db_session, current_user):
    raw_invite(db_session, "expirado-token", created_by=current_user.id, expires_delta=timedelta(days=-1))

    response = client.get("/invites/")
    assert response.json()["total"] == 0


def test_cria_convite_cancela_quem_criou(client, db_session, current_user):
    response = client.post("/invites/", json={"email": "cancelar@north.com"})
    invite_id = response.json()["id"]

    delete_response = client.delete(f"/invites/{invite_id}")
    assert delete_response.status_code == 204
    assert db_session.query(Invite).filter(Invite.id == invite_id).first() is None


def test_apenas_criador_ou_admin_cancela_convite(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    leader = make_leader(db_session, "lider-c6@north.com", ministry)

    response = client.post("/invites/", json={"email": "de-outro@north.com"})
    invite_id = response.json()["id"]

    app.dependency_overrides[get_current_user] = lambda: leader
    delete_response = client.delete(f"/invites/{invite_id}")
    assert delete_response.status_code == 403


# ---------------------------------------------------------------------------
# C3. Registro exigindo convite
# ---------------------------------------------------------------------------


def test_registro_sem_token_da_403(client):
    response = client.post(
        "/auth/register",
        json={"name": "Sem Convite", "email": "sem-convite@north.com", "password": "12345678"},
    )
    assert response.status_code == 403


def test_registro_com_token_invalido_da_403(client):
    response = client.post(
        "/auth/register",
        json={
            "name": "Invalido",
            "email": "invalido@north.com",
            "password": "12345678",
            "invite_token": "token-que-nao-existe",
        },
    )
    assert response.status_code == 403


def test_registro_com_token_expirado_e_usado_dao_mensagens_diferentes(client, db_session, current_user):
    raw_invite(db_session, "expirado", created_by=current_user.id, expires_delta=timedelta(days=-1))
    raw_invite(db_session, "usado", created_by=current_user.id, used_at=utcnow())

    expired_response = client.post(
        "/auth/register",
        json={
            "name": "A",
            "email": "a@north.com",
            "password": "12345678",
            "invite_token": "expirado",
        },
    )
    used_response = client.post(
        "/auth/register",
        json={
            "name": "B",
            "email": "b@north.com",
            "password": "12345678",
            "invite_token": "usado",
        },
    )

    assert expired_response.status_code == 403
    assert used_response.status_code == 403
    assert expired_response.json()["detail"] != used_response.json()["detail"]


def test_registro_com_convite_de_ministerio_cria_vinculo(client, db_session, current_user):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    raw_invite(
        db_session,
        "com-ministerio",
        created_by=current_user.id,
        email="novo@north.com",
        ministry_id=ministry.id,
        ministry_role=MinistryRole.LEADER,
    )

    response = client.post(
        "/auth/register",
        json={
            "name": "Novo",
            "email": "novo@north.com",
            "password": "12345678",
            "invite_token": "com-ministerio",
        },
    )
    assert response.status_code == 201
    new_user_id = response.json()["id"]

    membership = (
        db_session.query(MinistryMember)
        .filter(MinistryMember.ministry_id == ministry.id, MinistryMember.user_id == new_user_id)
        .first()
    )
    assert membership is not None
    assert membership.role == MinistryRole.LEADER

    new_user = db_session.query(User).filter(User.id == new_user_id).first()
    assert new_user.role == UserRole.LEADER  # regra de ouro (A3) aplicada no cadastro


def test_mesmo_token_nao_funciona_duas_vezes(client, db_session, current_user):
    raw_invite(db_session, "usar-uma-vez", created_by=current_user.id)

    first = client.post(
        "/auth/register",
        json={
            "name": "Primeiro",
            "email": "primeiro@north.com",
            "password": "12345678",
            "invite_token": "usar-uma-vez",
        },
    )
    assert first.status_code == 201

    second = client.post(
        "/auth/register",
        json={
            "name": "Segundo",
            "email": "segundo@north.com",
            "password": "12345678",
            "invite_token": "usar-uma-vez",
        },
    )
    assert second.status_code == 403


def test_convite_com_email_so_vale_para_aquele_email(client, db_session, current_user):
    raw_invite(db_session, "email-fixo", created_by=current_user.id, email="fixo@north.com")

    response = client.post(
        "/auth/register",
        json={
            "name": "Outro",
            "email": "outro@north.com",
            "password": "12345678",
            "invite_token": "email-fixo",
        },
    )
    assert response.status_code == 403


def test_lider_nao_pode_convidar_co_lider_pelo_papel_no_ministerio(client, db_session):
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.commit()
    leader = make_leader(db_session, "lider-co@north.com", ministry)
    app.dependency_overrides[get_current_user] = lambda: leader

    response = client.post(
        "/invites/",
        json={
            "role": "MEMBER",
            "ministry_id": ministry.id,
            "ministry_role": "LEADER",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only ADMIN can set a member as LEADER"
    assert db_session.query(Invite).count() == 0


def test_admin_pode_convidar_lider_de_ministerio(client, db_session):
    ministry = Ministry(name="Mídia")
    db_session.add(ministry)
    db_session.commit()

    response = client.post(
        "/invites/",
        json={
            "role": "MEMBER",
            "ministry_id": ministry.id,
            "ministry_role": "LEADER",
        },
    )

    assert response.status_code == 201
    assert response.json()["ministry_role"] == "LEADER"
