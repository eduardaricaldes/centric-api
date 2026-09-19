import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.dependencies import (
    get_current_user,
    require_admin,
    require_ministry_leader,
    require_roles,
)
from app.main import app
from app.models.ministry import Ministry
from app.models.ministry_member import MinistryMember
from app.models.roles import MinistryRole, UserRole
from app.models.user import User


def create_user(db_session, email: str, role: UserRole) -> User:
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


def test_require_roles_aceita_apenas_papeis_configurados(current_user):
    leader = User(
        name="Leader",
        email="leader@example.com",
        password_hash="x",
        role=UserRole.LEADER,
    )
    member = User(
        name="Member",
        email="member@example.com",
        password_hash="x",
        role=UserRole.MEMBER,
    )
    checker = require_roles("ADMIN", "LEADER")

    assert checker(current_user) is current_user
    assert checker(leader) is leader

    with pytest.raises(HTTPException) as exc_info:
        checker(member)

    assert exc_info.value.status_code == 403


def test_leader_global_nao_recebe_acesso_admin_sem_escopo_de_ministerio(
    client,
    db_session,
):
    leader = create_user(db_session, "route-leader@example.com", UserRole.LEADER)
    app.dependency_overrides.pop(require_admin)
    app.dependency_overrides[get_current_user] = lambda: leader

    response = client.post(
        "/songs/",
        json={"title": "Restrita", "lyrics": "Letra"},
    )

    assert response.status_code == 403


def test_admin_tem_acesso_a_qualquer_ministerio(current_user, db_session):
    assert require_ministry_leader(999, current_user, db_session) is current_user


def test_leader_so_gerencia_ministerio_em_que_e_lider(db_session):
    leader = create_user(db_session, "leader@example.com", UserRole.LEADER)
    own_ministry = Ministry(name="Louvor")
    other_ministry = Ministry(name="Pregação")
    db_session.add_all([own_ministry, other_ministry])
    db_session.flush()
    db_session.add(
        MinistryMember(
            ministry_id=own_ministry.id,
            user_id=leader.id,
            role=MinistryRole.LEADER,
            instrument="Violão",
        )
    )
    db_session.commit()

    assert require_ministry_leader(own_ministry.id, leader, db_session) is leader

    with pytest.raises(HTTPException) as exc_info:
        require_ministry_leader(other_ministry.id, leader, db_session)

    assert exc_info.value.status_code == 403


def test_member_global_nao_gerencia_ministerio_mesmo_com_vinculo_de_leader(
    db_session,
):
    member = create_user(db_session, "member@example.com", UserRole.MEMBER)
    ministry = Ministry(name="Mídia")
    db_session.add(ministry)
    db_session.flush()
    db_session.add(
        MinistryMember(
            ministry_id=ministry.id,
            user_id=member.id,
            role=MinistryRole.LEADER,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        require_ministry_leader(ministry.id, member, db_session)

    assert exc_info.value.status_code == 403


def test_usuario_nao_pode_ter_vinculo_duplicado_no_mesmo_ministerio(db_session):
    member = create_user(db_session, "duplicate@example.com", UserRole.MEMBER)
    ministry = Ministry(name="Recepção")
    db_session.add(ministry)
    db_session.flush()
    membership = MinistryMember(ministry_id=ministry.id, user_id=member.id)
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(membership)

    assert membership.role == MinistryRole.MEMBER

    db_session.add(MinistryMember(ministry_id=ministry.id, user_id=member.id))

    with pytest.raises(IntegrityError):
        db_session.commit()

    db_session.rollback()
