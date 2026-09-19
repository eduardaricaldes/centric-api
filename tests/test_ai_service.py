from types import SimpleNamespace

import pytest

from app.schemas.program import ProgramBlock, ProgramBlockType, ProgramDraft
from app.services.ai_service import (
    AIServiceUnavailableError,
    GeminiProgramSuggestionProvider,
)


def make_draft() -> ProgramDraft:
    return ProgramDraft(
        resumo="Abertura e mensagem",
        blocos=[
            ProgramBlock(
                ordem=1,
                tipo=ProgramBlockType.MUSIC,
                song_id=1,
                duracao_min=5,
            ),
            ProgramBlock(
                ordem=2,
                tipo=ProgramBlockType.PREACHING,
                titulo="Mensagem",
                duracao_min=55,
            ),
        ],
    )


def test_provider_exige_chave_sem_fazer_requisicao():
    provider = GeminiProgramSuggestionProvider(
        api_key=None,
        model_name="gemini-test",
        timeout_seconds=30,
    )

    with pytest.raises(AIServiceUnavailableError):
        provider.suggest({"catalog": []})


def test_provider_usa_schema_estruturado_e_timeout(monkeypatch):
    draft = make_draft()
    captured = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(parsed=draft, text=None)

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.models = FakeModels()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    monkeypatch.setattr("app.services.ai_service.genai.Client", FakeClient)
    provider = GeminiProgramSuggestionProvider(
        api_key="secret",
        model_name="gemini-test",
        timeout_seconds=12,
    )

    result = provider.suggest(
        {
            "briefing": "Culto de celebração",
            "catalog": [{"id": 1, "title": "Canção"}],
            "target_duration_minutes": 60,
        }
    )

    assert result == draft
    assert captured["client"]["api_key"] == "secret"
    assert captured["client"]["http_options"].timeout == 12_000
    assert captured["request"]["model"] == "gemini-test"
    assert captured["request"]["config"].response_schema is ProgramDraft
    assert "secret" not in captured["request"]["contents"]
