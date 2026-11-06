from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.roles import (
    InviteKind,
    invite_kind_type,
    ministry_role_type,
    user_role_type,
)


class Invite(Base):
    __tablename__ = "invites"

    id = Column(Integer, primary_key=True, index=True)
    kind = Column(invite_kind_type, nullable=False, default=InviteKind.INVITE)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)

    email = Column(String, nullable=True)
    role = Column(user_role_type, nullable=True)
    ministry_id = Column(
        Integer,
        ForeignKey("ministries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ministry_role = Column(ministry_role_type, nullable=True)
    instrument = Column(String(100), nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    ministry = relationship("Ministry")
    creator = relationship("User", foreign_keys=[created_by])
    user_used = relationship("User", foreign_keys=[used_by])
