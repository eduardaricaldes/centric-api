from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ProgramSuggestion(Base):
    __tablename__ = "program_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    briefing = Column(Text, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    response = Column(JSON, nullable=False)
    request_hash = Column(String(64), nullable=False, unique=True, index=True)
    provider_model = Column(String(100), nullable=False)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    applied_response = Column(JSON, nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    applied_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    playlist_id = Column(
        Integer,
        ForeignKey("playlists.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    event = relationship("Event", back_populates="program_suggestions")
    playlist = relationship("Playlist")
