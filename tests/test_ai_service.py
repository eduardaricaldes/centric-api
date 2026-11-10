import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors as genai_errors

from app.schemas.program import ProgramBlock, ProgramBlockType, ProgramDraft
from app.services.ai_service import (
    PROGRAM_SYSTEM_INSTRUCTION,
    AIInvalidResponseError,
    AIServiceUnavailableError,
    GeminiProgramDraft,
    GeminiProgramSuggestionProvider,
    ChainedProgramSuggestionProvider,
    OpenAICompatibleProgramSuggestionProvider,
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


@pytest.fixture()
def ai_settings(monkeypatch):
    """Configuração da cadeia com todas as chaves; cada teste tira o que quiser."""
    values = {
        "ai_provider": "gemini,groq,openrouter",
        "gemini_api_key": "gemini-secret",
        "gemini_model": "gemini-flash",
        "gemini_fallback_model": "gemini-lite",
        "groq_api_key": "groq-secret",
        "groq_model": "openai/gpt-oss-120b",
        "openrouter_api_key": "openrouter-secret",
        "openrouter_model": "vendor/model:free",
    }
    for name, value in values.items():
        monkeypatch.setattr(f"app.services.ai_service.settings.{name}", value)

    def set_value(name, value):
        monkeypatch.setattr(f"app.services.ai_service.settings.{name}", value)

    return set_value


def chain_labels(provider) -> list[str]:
    assert isinstance(provider, ChainedProgramSuggestionProvider)
    return [step.model_name for step in provider.providers]


def test_cadeia_completa_na_ordem_pedida(ai_settings):
    provider = get_program_suggestion_provider()

    assert chain_labels(provider) == [
        "gemini:gemini-flash",
        "gemini:gemini-lite",
        "groq:openai/gpt-oss-120b",
        "openrouter:vendor/model:free",
    ]
    assert provider.model_name == "gemini:gemini-flash"
    # Só o último degrau insiste; os outros passam a vez logo.
    assert [getattr(step, "attempts", None) for step in provider.providers] == [
        1,
        1,
        None,
        None,
    ]
    assert provider.providers[2].base_url == "https://api.groq.com/openai/v1"
    assert provider.providers[3].base_url == "https://openrouter.ai/api/v1"


@pytest.mark.parametrize(
    ("missing", "expected"),
    [
        ("groq_api_key", ["gemini:gemini-flash", "gemini:gemini-lite", "openrouter:vendor/model:free"]),
        ("openrouter_api_key", ["gemini:gemini-flash", "gemini:gemini-lite", "groq:openai/gpt-oss-120b"]),
        ("gemini_api_key", ["groq:openai/gpt-oss-120b", "openrouter:vendor/model:free"]),
        ("gemini_fallback_model", ["gemini:gemini-flash", "groq:openai/gpt-oss-120b", "openrouter:vendor/model:free"]),
    ],
)
def test_provedor_sem_chave_e_pulado(ai_settings, missing, expected):
    ai_settings(missing, None)

    assert chain_labels(get_program_suggestion_provider()) == expected


def test_reserva_igual_ao_principal_nao_duplica(ai_settings):
    ai_settings("gemini_fallback_model", "gemini-flash")
    ai_settings("groq_api_key", None)
    ai_settings("openrouter_api_key", None)

    provider = get_program_suggestion_provider()

    assert chain_labels(provider) == ["gemini:gemini-flash"]
    assert provider.providers[0].attempts == 3


def test_openrouter_com_modelo_pago_fica_fora(ai_settings, caplog):
    ai_settings("openrouter_model", "openai/gpt-5")

    with caplog.at_level(logging.ERROR):
        provider = get_program_suggestion_provider()

    assert "openrouter:openai/gpt-5" not in chain_labels(provider)
    assert "is not a :free model" in caplog.text


def test_ordem_e_nome_vem_de_ai_provider(ai_settings):
    ai_settings("ai_provider", " Groq , gemini ")

    assert chain_labels(get_program_suggestion_provider()) == [
        "groq:openai/gpt-oss-120b",
        "gemini:gemini-flash",
        "gemini:gemini-lite",
    ]


def test_sem_nenhum_provedor_fica_indisponivel_e_vai_para_o_log(ai_settings, caplog):
    ai_settings("ai_provider", "claude")

    with caplog.at_level(logging.ERROR):
        provider = get_program_suggestion_provider()

    assert isinstance(provider, UnconfiguredProgramSuggestionProvider)
    assert "Unknown AI_PROVIDER 'claude'" in caplog.text
    with pytest.raises(AIServiceUnavailableError):
        provider.suggest({"catalog": []})


# ---- Cadeia com HTTP mockado em cada degrau ----

DRAFT_JSON = json.dumps(
    {
        "resumo": "Abertura e mensagem",
        "blocos": [
            {"ordem": 1, "tipo": "MUSICA", "song_id": 1, "duracao_min": 5},
            {"ordem": 2, "tipo": "PREGACAO", "titulo": "Mensagem", "duracao_min": 55},
        ],
    }
)


def chat_response(content: str | None) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


class FakeGeminiAPI:
    """genai.Client falso: modelo -> ProgramDraft, código HTTP ou exceção."""

    def __init__(self, monkeypatch, outcomes: dict):
        self.calls: list[tuple[str, int]] = []
        api = self

        class FakeModels:
            def __init__(self, attempts):
                self.attempts = attempts

            def generate_content(self, **kwargs):
                model = kwargs["model"]
                api.calls.append((model, self.attempts))
                outcome = outcomes[model]
                if isinstance(outcome, int):
                    raise genai_errors.APIError(outcome, {"error": {"message": "x"}})
                if isinstance(outcome, Exception):
                    raise outcome
                return SimpleNamespace(parsed=outcome, text=None)

        class FakeClient:
            def __init__(self, **kwargs):
                self.models = FakeModels(kwargs["http_options"].retry_options.attempts)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        monkeypatch.setattr("app.services.ai_service.genai.Client", FakeClient)


class FakeOpenAIAPI:
    """Rotas /chat/completions falsas para Groq e OpenRouter."""

    def __init__(self, monkeypatch, outcomes: dict):
        self.requests: list[httpx.Request] = []
        api = self

        def handler(request: httpx.Request) -> httpx.Response:
            api.requests.append(request)
            outcome = outcomes[request.url.host]
            if callable(outcome):
                outcome = outcome(request)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        transport = httpx.MockTransport(handler)
        original = OpenAICompatibleProgramSuggestionProvider.__init__

        def init_with_mock(self, *args, **kwargs):
            original(self, *args, **kwargs)
            self.transport = transport

        monkeypatch.setattr(
            OpenAICompatibleProgramSuggestionProvider, "__init__", init_with_mock
        )

    def bodies(self, host: str) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.url.host == host]


GROQ = "api.groq.com"
OPENROUTER = "openrouter.ai"


def test_gemini_principal_responde(ai_settings, monkeypatch):
    gemini = FakeGeminiAPI(monkeypatch, {"gemini-flash": make_draft()})
    http = FakeOpenAIAPI(monkeypatch, {})
    provider = get_program_suggestion_provider()

    assert provider.suggest({"catalog": []}) == make_draft()
    assert provider.last_model_name == "gemini:gemini-flash"
    assert gemini.calls == [("gemini-flash", 1)]
    assert http.requests == []


@pytest.mark.parametrize(
    "failure",
    [429, 500, 503, 504, TimeoutError("read timed out")],
)
def test_gemini_principal_falha_e_reserva_responde(ai_settings, monkeypatch, failure):
    gemini = FakeGeminiAPI(
        monkeypatch,
        {"gemini-flash": failure, "gemini-lite": make_draft()},
    )
    provider = get_program_suggestion_provider()

    assert provider.suggest({"catalog": []}) == make_draft()
    assert provider.last_model_name == "gemini:gemini-lite"
    assert [model for model, _attempts in gemini.calls] == ["gemini-flash", "gemini-lite"]


def test_gemini_invalido_passa_para_o_reserva(ai_settings, monkeypatch):
    invalid = GeminiProgramDraft(
        resumo="Sem música",
        blocos=[{"ordem": 1, "tipo": "MUSICA", "duracao_min": 5}],
    )
    FakeGeminiAPI(monkeypatch, {"gemini-flash": invalid, "gemini-lite": make_draft()})
    provider = get_program_suggestion_provider()

    assert provider.suggest({"catalog": []}) == make_draft()
    assert provider.last_model_name == "gemini:gemini-lite"


def test_gemini_fora_e_groq_responde_com_json_schema(ai_settings, monkeypatch, caplog):
    FakeGeminiAPI(monkeypatch, {"gemini-flash": 429, "gemini-lite": 503})
    http = FakeOpenAIAPI(monkeypatch, {GROQ: chat_response(DRAFT_JSON)})
    provider = get_program_suggestion_provider()

    with caplog.at_level(logging.WARNING):
        result = provider.suggest({"briefing": "Culto", "catalog": []})

    assert result == make_draft()
    assert provider.last_model_name == "groq:openai/gpt-oss-120b"
    request = http.requests[0]
    assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer groq-secret"
    body = json.loads(request.content)
    assert body["model"] == "openai/gpt-oss-120b"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == (
        GeminiProgramDraft.model_json_schema()
    )
    assert body["messages"][0] == {
        "role": "system",
        "content": PROGRAM_SYSTEM_INSTRUCTION,
    }
    for secret in ("gemini-secret", "groq-secret", "openrouter-secret"):
        assert secret not in caplog.text


@pytest.mark.parametrize(
    "groq_outcome",
    [
        httpx.Response(429, json={"error": "rate limited"}),
        httpx.Response(500, text="boom"),
        httpx.Response(503, text="busy"),
        httpx.ReadTimeout("timed out"),
        httpx.ConnectError("no route"),
        chat_response('{"resumo": "sem blocos"}'),
        chat_response("isto não é JSON"),
        chat_response(None),
        httpx.Response(200, json={"unexpected": True}),
    ],
)
def test_groq_falha_e_openrouter_responde(ai_settings, monkeypatch, groq_outcome):
    FakeGeminiAPI(monkeypatch, {"gemini-flash": 503, "gemini-lite": 503})
    http = FakeOpenAIAPI(
        monkeypatch,
        {GROQ: groq_outcome, OPENROUTER: chat_response(DRAFT_JSON)},
    )
    provider = get_program_suggestion_provider()

    assert provider.suggest({"catalog": []}) == make_draft()
    assert provider.last_model_name == "openrouter:vendor/model:free"
    request = [r for r in http.requests if r.url.host == OPENROUTER][0]
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer openrouter-secret"
    body = json.loads(request.content)
    assert body["model"] == "vendor/model:free"
    assert body["provider"] == {"require_parameters": True}


def test_modelo_sem_json_schema_recebe_json_object_com_schema_no_prompt(
    ai_settings, monkeypatch
):
    ai_settings("ai_provider", "groq")

    def groq(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["response_format"]["type"] == "json_schema":
            return httpx.Response(400, json={"error": "response_format not supported"})
        return chat_response("```json\n" + DRAFT_JSON + "\n```")

    http = FakeOpenAIAPI(monkeypatch, {GROQ: groq})
    provider = get_program_suggestion_provider()

    assert provider.suggest({"catalog": []}) == make_draft()
    first, second = http.bodies(GROQ)
    assert first["response_format"]["type"] == "json_schema"
    assert second["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in second["messages"][1]["content"]
    assert '"duracao_min"' in second["messages"][1]["content"]


def test_campos_a_mais_na_resposta_sao_ignorados(ai_settings, monkeypatch):
    ai_settings("ai_provider", "groq")
    extra = json.loads(DRAFT_JSON)
    extra["observacao"] = "texto a mais"
    FakeOpenAIAPI(monkeypatch, {GROQ: chat_response(json.dumps(extra))})

    assert get_program_suggestion_provider().suggest({"catalog": []}) == make_draft()


def test_todos_indisponiveis_da_503(ai_settings, monkeypatch):
    FakeGeminiAPI(monkeypatch, {"gemini-flash": 429, "gemini-lite": 429})
    FakeOpenAIAPI(
        monkeypatch,
        {GROQ: httpx.Response(429), OPENROUTER: httpx.ReadTimeout("slow")},
    )
    provider = get_program_suggestion_provider()

    with pytest.raises(AIServiceUnavailableError):
        provider.suggest({"catalog": []})
    assert provider.last_model_name is None


def test_todos_invalidos_da_resposta_invalida(ai_settings, monkeypatch):
    ai_settings("ai_provider", "groq,openrouter")
    FakeOpenAIAPI(
        monkeypatch,
        {GROQ: chat_response("{}"), OPENROUTER: chat_response("[]")},
    )

    with pytest.raises(AIInvalidResponseError):
        get_program_suggestion_provider().suggest({"catalog": []})
