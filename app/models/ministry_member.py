from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.roles import MinistryRole, ministry_role_type


class MinistryMember(Base):
    __tablename__ = "ministry_members"
    __table_args__ = (
        UniqueConstraint(
            "ministry_id",
            "user_id",
            name="uq_ministry_members_ministry_user",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    ministry_id = Column(
        Integer,
        ForeignKey("ministries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        ministry_role_type,
        nullable=False,
        default=MinistryRole.MEMBER,
        server_default=MinistryRole.MEMBER.value,
    )
    instrument = Column(String(100), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    ministry = relationship("Ministry", back_populates="members")
    user = relationship("User", back_populates="ministry_memberships")
