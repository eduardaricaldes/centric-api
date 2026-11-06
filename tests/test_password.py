from datetime import timedelta

from app.core.dependencies import get_current_user
from app.core.security import hash_password, verify_password
from app.main import app
from app.models.invite import Invite, InviteKind
from app.models.roles import UserRole
from app.models.user import User
from app.services.invites import hash_token, utcnow


def create_user_with_password(
    db_session, email: str, password: str, role: UserRole = UserRole.MEMBER
) -> User:
    user = User(
        name=email.split("@")[0],
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_invite(db_session, created_by: int, email: str | None = None) -> str:
    token = "invite-token-" + (email or "generic")
    invite = Invite(
        kind=InviteKind.INVITE,
        token_hash=hash_token(token),
        email=email,
        role=UserRole.MEMBER,
        created_by=created_by,
        expires_at=utcnow() + timedelta(days=7),
    )
    db_session.add(invite)
    db_session.commit()
    return token


def test_registro_com_senha_curta_da_422(client, db_session, current_user):
    token = create_invite(db_session, current_user.id, "curta@north.com")

    response = client.post(
        "/auth/register",
        json={
            "name": "Curta",
            "email": "curta@north.com",
            "password": "1234567",
            "invite_token": token,
        },
    )
    assert response.status_code == 422


def test_troca_senha_com_senha_atual_correta(client, db_session):
    user = create_user_with_password(db_session, "trocar@north.com", "senha-antiga")
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.post(
        "/auth/change-password",
        json={"current_password": "senha-antiga", "new_password": "senha-nova"},
    )
    assert response.status_code == 204

    db_session.refresh(user)
    assert verify_password("senha-nova", user.password_hash)


def test_troca_senha_com_senha_atual_errada_da_400(client, db_session):
    user = create_user_with_password(db_session, "errada@north.com", "senha-certa")
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.post(
        "/auth/change-password",
        json={"current_password": "senha-errada", "new_password": "senha-nova"},
    )
    assert response.status_code == 400


def test_troca_senha_nova_curta_da_422(client, db_session):
    user = create_user_with_password(db_session, "curtanova@north.com", "senha-certa")
    app.dependency_overrides[get_current_user] = lambda: user

    response = client.post(
        "/auth/change-password",
        json={"current_password": "senha-certa", "new_password": "1234567"},
    )
    assert response.status_code == 422


def test_admin_gera_link_e_usuario_redefine_senha(client, db_session):
    user = create_user_with_password(db_session, "esqueceu@north.com", "senha-velha")

    response = client.post(f"/users/{user.id}/reset-password")
    assert response.status_code == 201
    token = response.json()["token"]

    reset_response = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "senha-recuperada"},
    )
    assert reset_response.status_code == 204

    db_session.refresh(user)
    assert verify_password("senha-recuperada", user.password_hash)


def test_token_de_redefinicao_usado_duas_vezes_falha_na_segunda(client, db_session):
    user = create_user_with_password(db_session, "duasvezes@north.com", "senha-velha")
    token = client.post(f"/users/{user.id}/reset-password").json()["token"]

    first = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "senha-nova-1"},
    )
    assert first.status_code == 204

    second = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "senha-nova-2"},
    )
    assert second.status_code == 403


def test_token_de_redefinicao_nao_serve_como_convite(client, db_session):
    user = create_user_with_password(db_session, "naoserve@north.com", "senha-velha")
    token = client.post(f"/users/{user.id}/reset-password").json()["token"]

    response = client.post(
        "/auth/register",
        json={
            "name": "X",
            "email": "novo-x@north.com",
            "password": "12345678",
            "invite_token": token,
        },
    )
    assert response.status_code == 403


def test_convite_nao_serve_como_token_de_redefinicao(client, db_session, current_user):
    token = create_invite(db_session, current_user.id, "convite-como-reset@north.com")

    response = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "12345678"},
    )
    assert response.status_code == 403
