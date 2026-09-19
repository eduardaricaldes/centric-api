from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Preaching(Base):
    __tablename__ = "preachings"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    preacher_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    theme = Column(String(255), nullable=False)
    bible_reference = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    event = relationship("Event", back_populates="preaching")
    preacher = relationship("User")
