from enum import StrEnum

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class AssignmentStatus(StrEnum):
    INVITED = "CONVIDADO"
    CONFIRMED = "CONFIRMADO"
    DECLINED = "RECUSADO"


assignment_status_type = SQLAlchemyEnum(
    AssignmentStatus,
    name="assignment_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    length=10,
    values_callable=lambda enum: [item.value for item in enum],
)


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    ministry_id = Column(
        Integer,
        ForeignKey("ministries.id"),
        nullable=False,
        index=True,
    )
    function = Column(String(100), nullable=False)
    status = Column(
        assignment_status_type,
        nullable=False,
        default=AssignmentStatus.INVITED,
        server_default=AssignmentStatus.INVITED.value,
    )
    responded_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    event = relationship("Event", back_populates="assignments")
    user = relationship("User")
    ministry = relationship("Ministry")
