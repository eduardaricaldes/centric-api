from enum import StrEnum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    Time,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class EventType(StrEnum):
    SUNDAY_SERVICE = "CULTO_DOMINGO"
    REHEARSAL = "ENSAIO"
    EVENT = "EVENTO"


class EventStatus(StrEnum):
    DRAFT = "RASCUNHO"
    PUBLISHED = "PUBLICADO"


event_type = SQLAlchemyEnum(
    EventType,
    name="event_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    length=13,
    values_callable=lambda enum: [item.value for item in enum],
)

event_status_type = SQLAlchemyEnum(
    EventStatus,
    name="event_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    length=9,
    values_callable=lambda enum: [item.value for item in enum],
)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    date = Column(Date, nullable=False, index=True)
    time = Column(Time, nullable=False)
    type = Column(event_type, nullable=False)
    status = Column(
        event_status_type,
        nullable=False,
        default=EventStatus.DRAFT,
        server_default=EventStatus.DRAFT.value,
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    assignments = relationship(
        "Assignment",
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="Assignment.id",
        passive_deletes=True,
    )
    preaching = relationship(
        "Preaching",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    playlist = relationship(
        "Playlist",
        back_populates="event",
        passive_deletes=True,
        uselist=False,
    )
