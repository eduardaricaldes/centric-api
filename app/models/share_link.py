from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class ShareLinkKind(StrEnum):
    SONG = "SONG"
    EVENT = "EVENT"


share_link_kind_type = SQLAlchemyEnum(
    ShareLinkKind,
    name="share_link_kind",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    length=5,
)


class ShareLink(Base):
    """Link público, só de leitura, para quem não tem conta ver letras.

    O token fica guardado em claro (e não em hash, como nos convites) para o
    site poder mostrar e copiar o link de novo. Ele só abre letra e cifra,
    que é o mesmo conteúdo que a pessoa receberia por mensagem.
    """

    __tablename__ = "share_links"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'SONG' AND song_id IS NOT NULL AND event_id IS NULL)"
            " OR (kind = 'EVENT' AND event_id IS NOT NULL AND song_id IS NULL)",
            name="ck_share_links_target",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    kind = Column(share_link_kind_type, nullable=False)
    song_id = Column(
        Integer,
        ForeignKey("songs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    song = relationship("Song")
    event = relationship("Event")
