from sqlalchemy.orm import Session

from app.models.ministry_member import MinistryMember
from app.models.roles import MinistryRole, UserRole
from app.models.user import User


def leads_any_ministry(db: Session, user: User) -> bool:
    return (
        db.query(MinistryMember)
        .filter(
            MinistryMember.user_id == user.id,
            MinistryMember.role == MinistryRole.LEADER,
        )
        .first()
        is not None
    )


def sync_global_role(db: Session, user: User) -> None:
    """Aplica a regra de ouro: papel global LEADER exige liderar >= 1 ministério.

    Chame na mesma transação, depois de flush(), logo após qualquer escrita em
    MinistryMember que possa mudar quem lidera o quê (criar, promover,
    rebaixar ou remover membro) — nunca duplique esta lógica nas rotas.
    """
    if user.role == UserRole.ADMIN:
        return

    if leads_any_ministry(db, user):
        user.role = UserRole.LEADER
    else:
        user.role = UserRole.MEMBER
