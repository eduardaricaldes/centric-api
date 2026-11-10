import pytest

from app.schemas.program import ProgramBlock, ProgramBlockType, ProgramDraft
from app.services.programs import (
    ProgramValidationError,
    adjust_program_durations,
    extract_requested_durations,
    polish_suggested_program,
    restore_missing_accents,
    validate_and_enrich_program,
)


def make_context(
    *,
    target: int = 60,
    catalog: list[dict] | None = None,
    briefing: str = "Culto de celebração",
) -> dict:
    return {
        "briefing": briefing,
        "target_duration_minutes": target,
        "catalog": catalog
        if catalog is not None
        else [
            {"id": 1, "title": "Celebrai", "category": "Celebração", "duration_min": 6},
            {"id": 2, "title": "Rendido", "category": "Adoração", "duration_min": None},
        ],
        "requested_durations": extract_requested_durations(briefing, target),
        "recent_song_history": [],
    }


def make_draft(*blocks: dict, resumo: str = "Resumo") -> ProgramDraft:
    return ProgramDraft(
        resumo=resumo,
        blocos=[ProgramBlock(ordem=i, **block) for i, block in enumerate(blocks, start=1)],
    )


def music(song_id: int, minutes: int = 5) -> dict:
    return {"tipo": ProgramBlockType.MUSIC, "song_id": song_id, "duracao_min": minutes}


def moment(title: str, minutes: int) -> dict:
    return {"tipo": ProgramBlockType.MOMENT, "titulo": title, "duracao_min": minutes}


def preaching(minutes: int, title: str = "Mensagem") -> dict:
    return {"tipo": ProgramBlockType.PREACHING, "titulo": title, "duracao_min": minutes}


@pytest.mark.parametrize(
    ("briefing", "expected"),
    [
        (
            "Abrir com celebração, ter um momento de oração e uma pregação de 30 minutos.",
            [{"termo": "pregação", "tipo": "PREGACAO", "duracao_min": 30}],
        ),
        (
            "Culto de 90 minutos com 20 minutos de louvor, momento de oração de "
            "10 min e pregação (35 min)",
            [
                {"termo": "louvor", "tipo": "MUSICA", "duracao_min": 20},
                {"termo": "oração", "tipo": "MOMENTO", "duracao_min": 10},
                {"termo": "pregação", "tipo": "PREGACAO", "duracao_min": 35},
            ],
        ),
        (
            "Ceia: 15 min. 40 minutos para a mensagem.",
            [
                {"termo": "ceia", "tipo": "MOMENTO", "duracao_min": 15},
                {"termo": "mensagem", "tipo": "PREGACAO", "duracao_min": 40},
            ],
        ),
        ("Culto de 60 minutos com tema gratidão", []),
        ("Pregação de 500 minutos", []),
    ],
)
def test_extrai_duracoes_pedidas_no_briefing(briefing, expected):
    assert extract_requested_durations(briefing, 90) == expected


def test_musica_usa_duracao_do_catalogo_e_momento_fecha_o_alvo():
    draft = make_draft(music(1), music(2), moment("Oração", 10), preaching(40))

    adjusted = adjust_program_durations(draft, make_context())

    assert [block.duracao_min for block in adjusted.blocos] == [6, 5, 9, 40]
    assert adjusted.alertas == [
        "A duração de “Oração” passou de 10 para 9 min para fechar o alvo de 60 min."
    ]
    assert [block.duracao_min for block in draft.blocos] == [5, 5, 10, 40]


def test_pregacao_pedida_no_briefing_e_respeitada():
    context = make_context(briefing="Culto com uma pregação de 30 minutos")
    draft = make_draft(music(1, 6), moment("Oração", 9), music(2), preaching(25), moment("Avisos", 10))

    adjusted = adjust_program_durations(draft, context)

    assert [block.duracao_min for block in adjusted.blocos] == [6, 9, 5, 30, 10]
    assert adjusted.alertas == []


def test_diferenca_sai_do_maior_momento():
    context = make_context(briefing="Culto com uma pregação de 30 minutos")
    draft = make_draft(music(1, 6), moment("Oração", 9), music(2), preaching(25), moment("Avisos", 15))

    adjusted = adjust_program_durations(draft, context)

    assert [block.duracao_min for block in adjusted.blocos] == [6, 9, 5, 30, 10]


def test_sem_momento_a_pregacao_nao_pedida_fecha_o_alvo():
    draft = make_draft(music(1), music(2), preaching(46))

    adjusted = adjust_program_durations(draft, make_context())

    assert [block.duracao_min for block in adjusted.blocos] == [6, 5, 49]


def test_momento_pedido_no_briefing_e_achado_pelo_titulo_sem_acento():
    context = make_context(briefing="Culto com momento de oração de 10 minutos e pregação")
    draft = make_draft(music(1, 6), moment("Momento de Oracao", 5), music(2), preaching(44))

    adjusted = adjust_program_durations(draft, context)

    assert [block.duracao_min for block in adjusted.blocos] == [6, 10, 5, 39]


def test_diferenca_longe_do_alvo_nao_e_mascarada():
    context = make_context()
    draft = make_draft(music(1), moment("Oração", 10), preaching(20))

    adjusted = adjust_program_durations(draft, context)

    assert [block.duracao_min for block in adjusted.blocos] == [6, 10, 20]
    with pytest.raises(ProgramValidationError):
        validate_and_enrich_program(adjusted, context)


def test_acentos_sao_repostos_quando_o_texto_vem_todo_sem_acento():
    draft = make_draft(
        {**moment("ORACAO de gratidao", 10), "motivo": "Musica de celebracao para as oracoes"},
        resumo="Programacao de gratidao e comunhao",
    )

    fixed = restore_missing_accents(draft)

    assert fixed.resumo == "Programação de gratidão e comunhão"
    assert fixed.blocos[0].titulo == "ORAÇÃO de gratidão"
    assert fixed.blocos[0].motivo == "Música de celebração para as orações"


def test_texto_ja_acentuado_fica_como_veio():
    draft = make_draft(moment("Oração e louvor ao Pai", 10), resumo="Culto em Callao")

    assert restore_missing_accents(draft) == draft


def test_palavra_ao_isolada_nao_ganha_til():
    draft = make_draft(moment("Louvor ao Rei", 10), resumo="Gratidao ao Senhor")

    fixed = restore_missing_accents(draft)

    assert fixed.resumo == "Gratidão ao Senhor"
    assert fixed.blocos[0].titulo == "Louvor ao Rei"


def test_polish_junta_acentos_e_duracoes():
    draft = make_draft(music(1), moment("Oracao", 10), preaching(40), resumo="Gratidao")

    polished = polish_suggested_program(draft, make_context())

    assert polished.resumo == "Gratidão"
    assert polished.blocos[1].titulo == "Oração"
    assert sum(block.duracao_min for block in polished.blocos) == 60
