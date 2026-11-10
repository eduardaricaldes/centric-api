import json
import logging
from types import SimpleNamespace

import pytest

from app.schemas.program import ProgramBlock, ProgramBlockType, ProgramDraft
from app.services.ai_service import (
    PROGRAM_SYSTEM_INSTRUCTION,
    AIInvalidResponseError,
    AIServiceUnavailableError,
    GeminiProgramDraft,
    GeminiProgramSuggestionProvider,
    UnconfiguredProgramSuggestionProvider,
    build_program_prompt,
    get_program_suggestion_provider,
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
    assert captured["request"]["config"].response_schema is GeminiProgramDraft
    assert captured["request"]["config"].system_instruction == PROGRAM_SYSTEM_INSTRUCTION
    assert "secret" not in captured["request"]["contents"]


def test_schema_enviado_a_gemini_nao_tem_o_que_ela_recusa():
    schema = json.dumps(GeminiProgramDraft.model_json_schema())

    for keyword in ("additionalProperties", "maxLength", "minLength", "maxItems", "minimum"):
        assert f'"{keyword}"' not in schema


def test_resposta_da_gemini_passa_pela_validacao_do_program_draft(monkeypatch):
    parsed = GeminiProgramDraft(
        resumo="Sem música",
        blocos=[{"ordem": 1, "tipo": "MUSICA", "duracao_min": 5}],
    )

    class FakeModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(parsed=parsed, text=None)

    class FakeClient:
        models = FakeModels()

        def __init__(self, **kwargs):
            pass

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

    with pytest.raises(AIInvalidResponseError):
        provider.suggest({"catalog": []})


def test_falha_da_gemini_fica_no_log_sem_expor_a_chave(monkeypatch, caplog):
    class FailingClient:
        def __init__(self, **kwargs):
            raise RuntimeError("400 INVALID_ARGUMENT")

    monkeypatch.setattr("app.services.ai_service.genai.Client", FailingClient)
    provider = GeminiProgramSuggestionProvider(
        api_key="secret",
        model_name="gemini-test",
        timeout_seconds=12,
    )

    with caplog.at_level(logging.ERROR), pytest.raises(AIServiceUnavailableError):
        provider.suggest({"catalog": []})

    assert "400 INVALID_ARGUMENT" in caplog.text
    assert "secret" not in caplog.text


def test_prompt_leva_categoria_duracao_historico_e_duracoes_pedidas():
    context = {
        "briefing": "Abrir com celebração e pregação de 30 minutos",
        "target_duration_minutes": 60,
        "catalog": [
            {"id": 1, "title": "Celebrai", "category": "Celebração", "duration_min": 6},
        ],
        "requested_durations": [
            {"termo": "pregação", "tipo": "PREGACAO", "duracao_min": 30}
        ],
        "recent_song_history": [
            {"song_id": 1, "title": "Celebrai", "category": "Celebração"}
        ],
    }

    prompt = build_program_prompt(context)

    assert '"category": "Celebração"' in prompt
    assert '"duration_min": 6' in prompt
    assert '"requested_durations": [{"duracao_min": 30' in prompt
    assert '"recent_song_history": [{"category": "Celebração"' in prompt
    # Acentos chegam como texto, não como \\u escapes.
    assert "\\u00e7" not in prompt


@pytest.mark.parametrize(
    "rule",
    [
        "acentuação correta",
        "duration_min",
        "requested_durations",
        "category",
        "recent_song_history",
    ],
)
def test_instrucao_do_sistema_cobre_as_regras_de_qualidade(rule):
    assert rule in PROGRAM_SYSTEM_INSTRUCTION


def test_schema_da_gemini_orienta_duracao_e_acentos():
    schema = json.dumps(GeminiProgramDraft.model_json_schema(), ensure_ascii=False)

    assert "duration_min da música no catalog" in schema
    assert "português com acentos" in schema


def test_provedor_padrao_e_a_gemini(monkeypatch):
    monkeypatch.setattr("app.services.ai_service.settings.ai_provider", "gemini")
    monkeypatch.setattr("app.services.ai_service.settings.gemini_model", "gemini-x")

    provider = get_program_suggestion_provider()

    assert isinstance(provider, GeminiProgramSuggestionProvider)
    assert provider.model_name == "gemini-x"


def test_nome_do_provedor_ignora_caixa_e_espacos(monkeypatch):
    monkeypatch.setattr("app.services.ai_service.settings.ai_provider", " Gemini ")

    assert isinstance(get_program_suggestion_provider(), GeminiProgramSuggestionProvider)


def test_provedor_desconhecido_fica_indisponivel_e_vai_para_o_log(monkeypatch, caplog):
    monkeypatch.setattr("app.services.ai_service.settings.ai_provider", "claude")

    with caplog.at_level(logging.ERROR):
        provider = get_program_suggestion_provider()

    assert isinstance(provider, UnconfiguredProgramSuggestionProvider)
    assert provider.model_name == "unconfigured:claude"
    assert "Unknown AI_PROVIDER 'claude'" in caplog.text
    with pytest.raises(AIServiceUnavailableError):
        provider.suggest({"catalog": []})
