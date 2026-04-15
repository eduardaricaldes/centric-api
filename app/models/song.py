from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class Song(Base):
    __tablename__= "songs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    artist: Mapped[str | None] = mapped_column(String(255),nullable=True)
    lyrics: Mapped[str | None] = mapped_column(Text,nullable=True)