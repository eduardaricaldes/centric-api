from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProgramBlockType(StrEnum):
    MUSIC = "MUSICA"
    MOMENT = "MOMENTO"
    PREACHING = "PREGACAO"


class ProgramBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ordem: int = Field(..., ge=1, description="Posição do bloco na programação")
    tipo: ProgramBlockType = Field(..., description="Tipo do bloco")
    song_id: int | None = Field(
        default=None,
        description="ID do catálogo, obrigatório somente em blocos MUSICA",
    )
    titulo: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Título, obrigatório em MOMENTO e PREGACAO",
    )
    duracao_min: int = Field(..., ge=1, le=300)
    motivo: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_block_fields(self):
        if self.tipo == ProgramBlockType.MUSIC and self.song_id is None:
            raise ValueError("MUSICA requires song_id")
        if self.tipo != ProgramBlockType.MUSIC:
            if self.song_id is not None:
                raise ValueError("Only MUSICA accepts song_id")
            if self.titulo is None:
                raise ValueError("MOMENTO and PREGACAO require titulo")
        return self


class ProgramDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resumo: str = Field(..., min_length=1, max_length=1000)
    blocos: list[ProgramBlock] = Field(..., min_length=1, max_length=50)
    alertas: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_order(self):
        orders = [block.ordem for block in self.blocos]
        if sorted(orders) != list(range(1, len(self.blocos) + 1)):
            raise ValueError("ordem must be sequential and unique, starting at 1")
        return self


class ProgramSuggestRequest(BaseModel):
    briefing: str = Field(..., min_length=10, max_length=4000)
    duracao_alvo_min: int = Field(default=90, ge=15, le=300)


class ProgramSuggestionResponse(ProgramDraft):
    suggestion_id: int
    event_id: int
    briefing: str
    duracao_alvo_min: int
    provider_model: str
    cached: bool
    created_at: datetime
    applied_at: datetime | None


class ProgramApplyRequest(BaseModel):
    suggestion_id: int
    programacao: ProgramDraft | None = None


class ProgramApplyResponse(BaseModel):
    suggestion_id: int
    playlist_id: int
    song_ids: list[int]
    applied_at: datetime
