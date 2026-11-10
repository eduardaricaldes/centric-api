from app.core.dependencies import get_current_user
from app.main import app
from app.models.assignment import Assignment
from app.models.ministry import Ministry
from app.models.playlist_song import PlaylistSong
from app.models.program_suggestion import ProgramSuggestion
from app.models.roles import UserRole
from app.models.user import User
from app.schemas.program import ProgramBlock, ProgramBlockType, ProgramDraft
from app.services.ai_service import (
    AIServiceUnavailableError,
    get_program_suggestion_provider,
)


class FakeProvider:
    model_name = "gemini-fake"

    def __init__(self, draft: ProgramDraft):
        self.draft = draft
        self.contexts = []

    def suggest(self, context: dict) -> ProgramDraft:
        self.contexts.append(context)
        return self.draft


class UnavailableProvider:
    model_name = "gemini-fake"

    def suggest(self, context: dict) -> ProgramDraft:
        raise AIServiceUnavailableError("offline")


def create_user(db_session, email: str, role: UserRole = UserRole.MEMBER) -> User:
    user = User(
        name=email.split("@", maxsplit=1)[0],
        email=email,
        password_hash="x",
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_event(client, *, title: str, date: str) -> dict:
    response = client.post(
        "/events/",
        json={
            "title": title,
            "date": date,
            "time": "19:00:00",
            "type": "CULTO",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def valid_draft(song_id: int, duration: int = 60) -> ProgramDraft:
    return ProgramDraft(
        resumo="Celebração seguida de mensagem",
        blocos=[
            ProgramBlock(
                ordem=1,
                tipo=ProgramBlockType.MUSIC,
                song_id=song_id,
                duracao_min=5,
                motivo="Abertura celebrativa",
            ),
            ProgramBlock(
                ordem=2,
                tipo=ProgramBlockType.PREACHING,
                titulo="Mensagem",
                duracao_min=duration - 5,
            ),
        ],
    )


def configure_provider(provider):
    app.dependency_overrides[get_program_suggestion_provider] = lambda: provider


def test_sugestao_inclui_contexto_historico_alerta_e_cache(
    client,
    db_session,
    song_ids,
):
    past_event = create_event(client, title="Culto anterior", date="2026-10-04")
    playlist = client.post(
        "/playlist/",
        json={
            "title": "Repertório anterior",
            "date": "2026-10-04",
            "event_id": past_event["id"],
        },
    ).json()
    client.post(
        f"/playlist/{playlist['id']}/songs/",
        json={"song_id": song_ids[0]},
    )

    target_event = create_event(client, title="Culto alvo", date="2026-10-18")
    volunteer = create_user(db_session, "program-volunteer@example.com")
    ministry = Ministry(name="Louvor")
    db_session.add(ministry)
    db_session.flush()
    db_session.add(
        Assignment(
            event_id=target_event["id"],
            user_id=volunteer.id,
            ministry_id=ministry.id,
            function="Vocal",
        )
    )
    db_session.commit()

    provider = FakeProvider(valid_draft(song_ids[0]))
    configure_provider(provider)
    payload = {
        "briefing": "Culto celebrativo com mensagem sobre graça",
        "duracao_alvo_min": 60,
    }

    first = client.post(
        f"/events/{target_event['id']}/program/suggest",
        json=payload,
    )
    second = client.post(
        f"/events/{target_event['id']}/program/suggest",
        json=payload,
    )

    assert first.status_code == 201, first.text
    assert first.json()["cached"] is False
    assert first.json()["alertas"] == [
        "A música Ousado Amor foi usada em 2026-10-04."
    ]
    assert second.status_code == 201
    assert second.json()["cached"] is True
    assert second.json()["suggestion_id"] == first.json()["suggestion_id"]
    assert len(provider.contexts) == 1

    context = provider.contexts[0]
    assert context["target_duration_minutes"] == 60
    assert context["assignments"][0]["function"] == "Vocal"
    assert context["recent_song_history"][0]["song_id"] == song_ids[0]
    assert set(context["catalog"][0]) == {
        "id",
        "title",
        "tone",
        "category",
        "duration_min",
    }
    assert context["catalog"][0]["category"] == "Adoração"
    assert context["recent_song_history"][0]["category"] == "Adoração"
    assert context["requested_durations"] == []
    assert db_session.query(ProgramSuggestion).count() == 1


def test_rejeita_resposta_da_ia_com_song_id_fora_do_catalogo(
    client,
    db_session,
    song_ids,
):
    event = create_event(client, title="Culto inválido", date="2026-11-01")
    provider = FakeProvider(valid_draft(999))
    configure_provider(provider)

    response = client.post(
        f"/events/{event['id']}/program/suggest",
        json={
            "briefing": "Culto com uma programação inválida",
            "duracao_alvo_min": 60,
        },
    )

    assert response.status_code == 502
    assert "Unknown song_id" in response.json()["detail"]
    assert db_session.query(ProgramSuggestion).count() == 0


def test_falha_da_ia_nao_altera_playlist(client, db_session, song_ids):
    event = create_event(client, title="Culto offline", date="2026-11-08")
    playlist = client.post(
        "/playlist/",
        json={
            "title": "Manual",
            "date": "2026-11-08",
            "event_id": event["id"],
        },
    ).json()
    client.post(
        f"/playlist/{playlist['id']}/songs/",
        json={"song_id": song_ids[0]},
    )
    configure_provider(UnavailableProvider())

    response = client.post(
        f"/events/{event['id']}/program/suggest",
        json={
            "briefing": "Culto que continuará no modo manual",
            "duracao_alvo_min": 60,
        },
    )

    assert response.status_code == 503
    items = (
        db_session.query(PlaylistSong)
        .filter(PlaylistSong.playlist_id == playlist["id"])
        .all()
    )
    assert [item.song_id for item in items] == [song_ids[0]]
    assert db_session.query(ProgramSuggestion).count() == 0


def test_apply_substitui_playlist_somente_apos_revisao(
    client,
    db_session,
    song_ids,
):
    event = create_event(client, title="Culto para aplicar", date="2026-11-15")
    playlist = client.post(
        "/playlist/",
        json={
            "title": "Repertório revisável",
            "date": "2026-11-15",
            "event_id": event["id"],
        },
    ).json()
    client.post(
        f"/playlist/{playlist['id']}/songs/",
        json={"song_id": song_ids[0]},
    )

    provider = FakeProvider(valid_draft(song_ids[0]))
    configure_provider(provider)
    suggestion = client.post(
        f"/events/{event['id']}/program/suggest",
        json={
            "briefing": "Culto com revisão humana antes de aplicar",
            "duracao_alvo_min": 60,
        },
    ).json()

    edited = valid_draft(song_ids[1]).model_dump(mode="json")
    response = client.post(
        f"/events/{event['id']}/program/apply",
        json={
            "suggestion_id": suggestion["suggestion_id"],
            "programacao": edited,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["playlist_id"] == playlist["id"]
    assert response.json()["song_ids"] == [song_ids[1]]

    db_session.expire_all()
    items = (
        db_session.query(PlaylistSong)
        .filter(PlaylistSong.playlist_id == playlist["id"])
        .order_by(PlaylistSong.position)
        .all()
    )
    assert [item.song_id for item in items] == [song_ids[1]]
    saved = db_session.get(ProgramSuggestion, suggestion["suggestion_id"])
    assert saved.applied_at is not None
    assert saved.applied_response["blocos"][0]["song_id"] == song_ids[1]

    repeated = client.post(
        f"/events/{event['id']}/program/apply",
        json={"suggestion_id": suggestion["suggestion_id"]},
    )
    assert repeated.status_code == 409


def test_apply_invalido_preserva_playlist_existente(client, db_session, song_ids):
    event = create_event(client, title="Culto protegido", date="2026-11-22")
    playlist = client.post(
        "/playlist/",
        json={
            "title": "Repertório protegido",
            "date": "2026-11-22",
            "event_id": event["id"],
        },
    ).json()
    client.post(
        f"/playlist/{playlist['id']}/songs/",
        json={"song_id": song_ids[0]},
    )
    provider = FakeProvider(valid_draft(song_ids[1]))
    configure_provider(provider)
    suggestion = client.post(
        f"/events/{event['id']}/program/suggest",
        json={
            "briefing": "Culto cuja edição será inválida",
            "duracao_alvo_min": 60,
        },
    ).json()

    invalid = valid_draft(song_ids[1], duration=30).model_dump(mode="json")
    response = client.post(
        f"/events/{event['id']}/program/apply",
        json={
            "suggestion_id": suggestion["suggestion_id"],
            "programacao": invalid,
        },
    )

    assert response.status_code == 422
    db_session.expire_all()
    items = (
        db_session.query(PlaylistSong)
        .filter(PlaylistSong.playlist_id == playlist["id"])
        .all()
    )
    assert [item.song_id for item in items] == [song_ids[0]]


def test_qualquer_lider_pode_sugerir_programa_para_qualquer_evento(
    client,
    db_session,
    song_ids,
):
    event = create_event(client, title="Culto do admin", date="2026-11-29")
    other_leader = create_user(
        db_session,
        "other-program-leader@example.com",
        UserRole.LEADER,
    )
    app.dependency_overrides[get_current_user] = lambda: other_leader
    provider = FakeProvider(valid_draft(song_ids[0]))
    configure_provider(provider)

    response = client.post(
        f"/events/{event['id']}/program/suggest",
        json={
            "briefing": "Líder colaborando no evento de outro",
            "duracao_alvo_min": 60,
        },
    )

    assert response.status_code == 201


def test_membro_nao_pode_sugerir_programa(client, db_session, song_ids):
    event = create_event(client, title="Culto do admin", date="2026-11-30")
    member = create_user(db_session, "member-prog@example.com", UserRole.MEMBER)
    app.dependency_overrides[get_current_user] = lambda: member
    provider = FakeProvider(valid_draft(song_ids[0]))
    configure_provider(provider)

    response = client.post(
        f"/events/{event['id']}/program/suggest",
        json={"briefing": "Tentativa de acesso indevido", "duracao_alvo_min": 60},
    )

    assert response.status_code == 403, response.text


def test_duracao_perto_do_alvo_e_completada_com_alerta(client, db_session, song_ids):
    event = create_event(client, title="Culto tolerante", date="2026-11-29")
    configure_provider(FakeProvider(valid_draft(song_ids[0], duration=57)))

    response = client.post(
        f"/events/{event['id']}/program/suggest",
        json={"briefing": "Culto que soma quase o alvo", "duracao_alvo_min": 60},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert [block["duracao_min"] for block in body["blocos"]] == [5, 55]
    assert (
        "A duração de “Mensagem” passou de 52 para 55 min para fechar o alvo de 60 min."
        in body["alertas"]
    )


def test_edicao_do_lider_perto_do_alvo_passa_com_alerta(client, db_session, song_ids):
    event = create_event(client, title="Culto editado", date="2026-11-29")
    configure_provider(FakeProvider(valid_draft(song_ids[0])))
    suggestion = client.post(
        f"/events/{event['id']}/program/suggest",
        json={"briefing": "Culto que o líder vai encurtar", "duracao_alvo_min": 60},
    ).json()

    response = client.post(
        f"/events/{event['id']}/program/apply",
        json={
            "suggestion_id": suggestion["suggestion_id"],
            "programacao": valid_draft(song_ids[0], duration=57).model_dump(mode="json"),
        },
    )

    assert response.status_code == 200, response.text
    saved = db_session.get(ProgramSuggestion, suggestion["suggestion_id"])
    assert [block["duracao_min"] for block in saved.applied_response["blocos"]] == [5, 52]
    assert "A programação soma 57 min; o alvo era 60 min." in saved.applied_response["alertas"]


def test_duracao_longe_do_alvo_e_rejeitada(client, db_session, song_ids):
    event = create_event(client, title="Culto curto", date="2026-11-30")
    configure_provider(FakeProvider(valid_draft(song_ids[0], duration=50)))

    response = client.post(
        f"/events/{event['id']}/program/suggest",
        json={"briefing": "Culto que fica longe do alvo", "duracao_alvo_min": 60},
    )

    assert response.status_code == 502


def test_pedir_de_novo_depois_de_aplicar_gera_outra_sugestao(client, db_session, song_ids):
    event = create_event(client, title="Culto refeito", date="2026-12-06")
    provider = FakeProvider(valid_draft(song_ids[0]))
    configure_provider(provider)
    body = {"briefing": "Culto que será refeito", "duracao_alvo_min": 60}

    first = client.post(f"/events/{event['id']}/program/suggest", json=body).json()
    client.post(
        f"/events/{event['id']}/program/apply",
        json={"suggestion_id": first["suggestion_id"]},
    )
    second = client.post(f"/events/{event['id']}/program/suggest", json=body)

    assert second.status_code == 201, second.text
    assert second.json()["cached"] is False
    assert second.json()["suggestion_id"] != first["suggestion_id"]
    assert len(provider.contexts) == 2

    applied = client.post(
        f"/events/{event['id']}/program/apply",
        json={"suggestion_id": second.json()["suggestion_id"]},
    )
    assert applied.status_code == 200, applied.text


def test_programacao_aplicada_pode_ser_lida_por_membro(client, db_session, song_ids):
    event = create_event(client, title="Culto lido", date="2026-12-13")
    configure_provider(FakeProvider(valid_draft(song_ids[0])))

    assert client.get(f"/events/{event['id']}/program").status_code == 404

    suggestion = client.post(
        f"/events/{event['id']}/program/suggest",
        json={"briefing": "Culto com pregação", "duracao_alvo_min": 60},
    ).json()
    client.post(
        f"/events/{event['id']}/program/apply",
        json={"suggestion_id": suggestion["suggestion_id"]},
    )

    member = create_user(db_session, "leitor@north.com")
    app.dependency_overrides[get_current_user] = lambda: member
    response = client.get(f"/events/{event['id']}/program")

    assert response.status_code == 200, response.text
    assert [block["tipo"] for block in response.json()["blocos"]] == ["MUSICA", "PREGACAO"]
    assert response.json()["applied_at"] is not None


def test_programacao_de_evento_inexistente_da_404(client):
    assert client.get("/events/999/program").status_code == 404


PRODUCTION_BRIEFING = (
    "Culto de domingo à noite com tema gratidão. Abrir com celebração, ter um "
    "momento de oração e uma pregação de 30 minutos."
)


def create_song(client, title: str, category: str, duration_min: int | None) -> int:
    payload = {"title": title, "lyrics": f"letra de {title}", "category": category}
    if duration_min is not None:
        payload["duration_min"] = duration_min
    response = client.post("/songs/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def production_like_draft(songs: list[int]) -> ProgramDraft:
    """Como no teste em produção: tudo 5 min, pregação de 25 e sem acentos."""
    return ProgramDraft(
        resumo="Programacao de gratidao com celebracao e oracao",
        blocos=[
            ProgramBlock(ordem=1, tipo=ProgramBlockType.MUSIC, song_id=songs[0], duracao_min=5),
            ProgramBlock(ordem=2, tipo=ProgramBlockType.MUSIC, song_id=songs[1], duracao_min=5),
            ProgramBlock(
                ordem=3,
                tipo=ProgramBlockType.MOMENT,
                titulo="Momento de Oracao",
                duracao_min=15,
            ),
            ProgramBlock(ordem=4, tipo=ProgramBlockType.MUSIC, song_id=songs[2], duracao_min=5),
            ProgramBlock(
                ordem=5,
                tipo=ProgramBlockType.PREACHING,
                titulo="Pregacao: Gratidao",
                duracao_min=25,
            ),
            ProgramBlock(ordem=6, tipo=ProgramBlockType.MUSIC, song_id=songs[3], duracao_min=5),
        ],
    )


def test_sugestao_corrige_duracoes_e_acentos_do_teste_em_producao(client, db_session):
    songs = [
        create_song(client, "Celebrai", "Celebração", 6),
        create_song(client, "Alegria", "Celebração", 4),
        create_song(client, "Rendido", "Adoração", 5),
        create_song(client, "Sem Duração", "Adoração", None),
    ]
    event = create_event(client, title="Culto de gratidão", date="2026-12-20")
    provider = FakeProvider(production_like_draft(songs))
    configure_provider(provider)

    response = client.post(
        f"/events/{event['id']}/program/suggest",
        json={"briefing": PRODUCTION_BRIEFING, "duracao_alvo_min": 60},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    durations = [block["duracao_min"] for block in body["blocos"]]
    # Músicas com duração do catálogo (6 e 4), a sem duração fica com 5,
    # pregação de 30 como pedido e a oração fecha o alvo.
    assert durations == [6, 4, 10, 5, 30, 5]
    assert sum(durations) == 60
    assert body["resumo"] == "Programação de gratidão com celebração e oração"
    assert body["blocos"][2]["titulo"] == "Momento de Oração"
    assert body["blocos"][4]["titulo"] == "Pregação: Gratidão"
    assert body["alertas"] == [
        "A duração de “Momento de Oração” passou de 15 para 10 min para fechar "
        "o alvo de 60 min."
    ]

    context = provider.contexts[0]
    assert context["requested_durations"] == [
        {"termo": "pregação", "tipo": "PREGACAO", "duracao_min": 30}
    ]
    catalog = {song["id"]: song for song in context["catalog"]}
    assert catalog[songs[0]]["duration_min"] == 6
    assert catalog[songs[0]]["category"] == "Celebração"
    assert catalog[songs[3]]["duration_min"] is None


def test_edicao_do_lider_mantem_duracao_diferente_do_catalogo(client, db_session):
    song = create_song(client, "Versão Longa", "Celebração", 6)
    event = create_event(client, title="Culto com versão longa", date="2026-12-27")
    configure_provider(FakeProvider(valid_draft(song)))
    suggestion = client.post(
        f"/events/{event['id']}/program/suggest",
        json={"briefing": "Culto com uma versão estendida", "duracao_alvo_min": 60},
    ).json()
    edited = valid_draft(song).model_dump(mode="json")
    edited["blocos"][0]["duracao_min"] = 10
    edited["blocos"][1]["duracao_min"] = 50

    response = client.post(
        f"/events/{event['id']}/program/apply",
        json={"suggestion_id": suggestion["suggestion_id"], "programacao": edited},
    )

    assert response.status_code == 200, response.text
    saved = db_session.get(ProgramSuggestion, suggestion["suggestion_id"])
    assert saved.applied_response["blocos"][0]["duracao_min"] == 10


class FallbackProvider(FakeProvider):
    """Simula o principal sem cota e o reserva respondendo."""

    model_name = "gemini:gemini-flash"

    def suggest(self, context: dict) -> ProgramDraft:
        self.last_model_name = "groq:openai/gpt-oss-120b"
        return super().suggest(context)


def test_provider_model_salvo_e_o_modelo_que_respondeu(client, db_session, song_ids):
    event = create_event(client, title="Culto com reserva", date="2027-01-03")
    configure_provider(FallbackProvider(valid_draft(song_ids[0])))
    body = {"briefing": "Culto com o modelo principal sem cota", "duracao_alvo_min": 60}

    response = client.post(f"/events/{event['id']}/program/suggest", json=body)

    assert response.status_code == 201, response.text
    assert response.json()["provider_model"] == "groq:openai/gpt-oss-120b"
    saved = db_session.get(ProgramSuggestion, response.json()["suggestion_id"])
    assert saved.provider_model == "groq:openai/gpt-oss-120b"
