from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.database import Base


class LiveState(Base):
    """O que está no telão agora, para o celular acompanhar (Fase 4).

    Uma linha por evento. O telão não depende disto: ele conversa com o operador
    pelo navegador. Isto só serve para os celulares.
    """

    __tablename__ = "live_states"

    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    # slide | black | logo
    mode = Column(String(10), nullable=False, default="logo")
    song_index = Column(Integer, nullable=True)
    slide_index = Column(Integer, nullable=True)
    song_title = Column(String(255), nullable=True)
    # Linhas do slide, separadas por \n.
    lines = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
