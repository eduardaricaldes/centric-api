import hashlib
import json
import re
import unicodedata
from datetime import timedelta

from sqlalchemy.orm import Session, selectinload

from app.models.assignment import Assignment
from app.models.event import Event
from app.models.playlist import Playlist
from app.models.playlist_song import PlaylistSong
from app.models.song import Song
from app.schemas.program import ProgramBlockType, ProgramDraft

RECENT_HISTORY_DAYS = 28

# Palavras do briefing (sem acento, minúsculas) que indicam o tipo do bloco.
PREACHING_TERMS = {"pregacao", "mensagem", "palavra", "ministracao", "sermao"}
MUSIC_TERMS = {"louvor", "musica", "musicas", "cancao", "cancoes", "cantico", "canticos"}
# Palavras que aparecem antes de "N minutos" sem nomear um bloco.
NON_BLOCK_TERMS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "com",
    "em", "e", "por", "para", "cerca", "ate", "maximo", "minimo", "total",
    "aproximadamente", "culto", "programacao", "evento", "reuniao", "servico",
}
_TERM = r"(?P<term>[^\W\d_]+)"
_MINUTES = r"(?P<minutes>\d{1,3})\s*(?:minutos?|min)\b"
REQUESTED_DURATION_PATTERNS = (
    # "pregação de 30 minutos", "oração (10 min)", "pregação: 30 min"
    re.compile(_TERM + r"\s*(?:de|com|:|\(|-|–)?\s*" + _MINUTES, re.IGNORECASE),
    # "30 minutos de pregação", "10 min para a oração"
    re.compile(
        _MINUTES + r"\s+(?:de|para)\s+(?:(?:a|o|uma|um)\s+)?" + _TERM,
        re.IGNORECASE,
    ),
)


class ProgramValidationError(ValueError):
    pass


def get_duration_tolerance(target_minutes: int) -> int:
    """A IA erra a soma com frequência; quem decide é o líder, que vê o alerta."""
    return max(5, round(target_minutes * 0.15))


def get_recently_used_song_ids(db: Session, event: Event) -> set[int]:
    """Returns IDs of songs used in the RECENT_HISTORY_DAYS before this event's date."""
    history_start = event.date - timedelta(days=RECENT_HISTORY_DAYS)
    rows = (
        db.query(PlaylistSong.song_id)
        .join(Playlist, Playlist.id == PlaylistSong.playlist_id)
        .join(Event, Event.id == Playlist.event_id)
        .filter(Event.date >= history_start, Event.date < event.date)
        .all()
    )
    return {row.song_id for row in rows}


def fold_text(text: str) -> str:
    """Minúsculas e sem acento, para comparar "Oração" com "oracao"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def extract_requested_durations(briefing: str, target_minutes: int) -> list[dict]:
    """Acha no briefing durações pedidas, como "pregação de 30 minutos"."""
    found: list[tuple[int, dict]] = []
    seen_terms: set[str] = set()
    for pattern in REQUESTED_DURATION_PATTERNS:
        for match in pattern.finditer(briefing):
            term = match.group("term")
            folded = fold_text(term)
            minutes = int(match.group("minutes"))
            if folded in NON_BLOCK_TERMS or folded in seen_terms:
                continue
            if not 1 <= minutes <= target_minutes:
                continue
            if folded in PREACHING_TERMS:
                block_type = ProgramBlockType.PREACHING
            elif folded in MUSIC_TERMS:
                block_type = ProgramBlockType.MUSIC
            else:
                block_type = ProgramBlockType.MOMENT
            seen_terms.add(folded)
            found.append(
                (
                    match.start(),
                    {
                        "termo": term.lower(),
                        "tipo": block_type.value,
                        "duracao_min": minutes,
                    },
                )
            )
    return [item for _start, item in sorted(found, key=lambda pair: pair[0])]


def build_program_context(
    db: Session,
    event: Event,
    briefing: str,
    duration_minutes: int,
) -> dict:
    songs = db.query(Song).order_by(Song.id).all()
    assignments = (
        db.query(Assignment)
        .options(
            selectinload(Assignment.user),
            selectinload(Assignment.ministry),
        )
        .filter(Assignment.event_id == event.id)
        .order_by(Assignment.id)
        .all()
    )
    history_start = event.date - timedelta(days=RECENT_HISTORY_DAYS)
    history_rows = (
        db.query(PlaylistSong, Song, Event)
        .join(Playlist, Playlist.id == PlaylistSong.playlist_id)
        .join(Event, Event.id == Playlist.event_id)
        .join(Song, Song.id == PlaylistSong.song_id)
        .filter(Event.date >= history_start, Event.date < event.date)
        .order_by(Event.date.desc(), PlaylistSong.position)
        .all()
    )

    preaching = event.preaching
    return {
        "event": {
            "id": event.id,
            "title": event.title,
            "date": event.date.isoformat(),
            "time": event.time.isoformat(),
            "type": event.type.value,
            "preaching": (
                {
                    "theme": preaching.theme,
                    "bible_reference": preaching.bible_reference,
                }
                if preaching is not None
                else None
            ),
        },
        "briefing": briefing,
        "target_duration_minutes": duration_minutes,
        "catalog": [
            {
                "id": song.id,
                "title": song.title,
                "tone": song.tone,
                "category": song.category,
                "duration_min": song.duration_min,
            }
            for song in songs
        ],
        "requested_durations": extract_requested_durations(briefing, duration_minutes),
        "assignments": [
            {
                "user": assignment.user.name,
                "ministry": assignment.ministry.name,
                "function": assignment.function,
                "status": assignment.status.value,
            }
            for assignment in assignments
        ],
        "recent_song_history": [
            {
                "song_id": song.id,
                "title": song.title,
                "category": song.category,
                "event_id": previous_event.id,
                "event_date": previous_event.date.isoformat(),
            }
            for _item, song, previous_event in history_rows
        ],
    }


def get_request_hash(context: dict, model_name: str) -> str:
    payload = {"model": model_name, "context": context}
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find_requested_block(blocks: list, request: dict) -> int | None:
    """Índice do único bloco que corresponde ao pedido; None se ambíguo."""
    if request["tipo"] == ProgramBlockType.PREACHING.value:
        candidates = [
            index
            for index, block in enumerate(blocks)
            if block.tipo == ProgramBlockType.PREACHING
        ]
    elif request["tipo"] == ProgramBlockType.MOMENT.value:
        term = fold_text(request["termo"])
        candidates = [
            index
            for index, block in enumerate(blocks)
            if block.tipo == ProgramBlockType.MOMENT
            and term in fold_text(block.titulo or "")
        ]
    else:
        # Tempo de louvor é a soma de várias músicas: fica só no prompt.
        return None
    return candidates[0] if len(candidates) == 1 else None


def _block_label(block, catalog: dict) -> str:
    if block.tipo == ProgramBlockType.MUSIC and block.song_id in catalog:
        return catalog[block.song_id]["title"]
    return block.titulo or block.tipo.value


def adjust_program_durations(draft: ProgramDraft, context: dict) -> ProgramDraft:
    """Corrige o que o modelo erra com frequência, antes da validação.

    1. Música com duração cadastrada usa a do catálogo.
    2. Duração pedida no briefing (pregação de 30 min) é respeitada.
    3. A diferença que sobra para o alvo vai para os blocos MOMENTO e, sem
       eles, para a pregação que o briefing não fixou. Só ajusta quando a
       diferença está dentro da tolerância: longe disso, a resposta continua
       sendo recusada pela validação.
    """
    adjusted = draft.model_copy(deep=True)
    blocks = adjusted.blocos
    catalog = {song["id"]: song for song in context["catalog"]}
    locked: set[int] = set()

    for index, block in enumerate(blocks):
        if block.tipo != ProgramBlockType.MUSIC:
            continue
        locked.add(index)
        song = catalog.get(block.song_id)
        if song is not None and song.get("duration_min"):
            block.duracao_min = song["duration_min"]

    for request in context.get("requested_durations", []):
        index = _find_requested_block(blocks, request)
        if index is None or index in locked:
            continue
        blocks[index].duracao_min = request["duracao_min"]
        locked.add(index)

    target = context["target_duration_minutes"]
    missing = target - sum(block.duracao_min for block in blocks)
    if missing == 0 or abs(missing) > get_duration_tolerance(target):
        return adjusted

    flexible_groups = [
        [
            index
            for index, block in enumerate(blocks)
            if block.tipo == block_type and index not in locked
        ]
        for block_type in (ProgramBlockType.MOMENT, ProgramBlockType.PREACHING)
    ]
    for group in flexible_groups:
        for index in sorted(group, key=lambda i: -blocks[i].duracao_min):
            if missing == 0:
                break
            block = blocks[index]
            new_duration = min(300, max(1, block.duracao_min + missing))
            if new_duration == block.duracao_min:
                continue
            adjusted.alertas.append(
                f"A duração de “{_block_label(block, catalog)}” passou de "
                f"{block.duracao_min} para {new_duration} min para fechar "
                f"o alvo de {target} min."
            )
            missing -= new_duration - block.duracao_min
            block.duracao_min = new_duration
    return adjusted


# Formas sem acento que o modelo às vezes devolve (comparadas sem caixa).
UNACCENTED_WORDS = {
    "ate": "até", "apos": "após", "biblia": "bíblia", "biblica": "bíblica",
    "cantico": "cântico", "canticos": "cânticos", "catalogo": "catálogo",
    "espirito": "espírito", "familia": "família", "fe": "fé",
    "gloria": "glória", "graca": "graça", "gracas": "graças",
    "historico": "histórico", "mao": "mão", "ministerio": "ministério",
    "misericordia": "misericórdia", "musica": "música", "musicas": "músicas",
    "nao": "não", "ofertorio": "ofertório", "pao": "pão",
    "proposito": "propósito", "sao": "são", "tambem": "também",
    "unica": "única", "unico": "único", "voce": "você",
}
UNACCENTED_SUFFIXES = (
    (re.compile(r"(?<=[a-z]{2})coes$"), "ções"),
    (re.compile(r"(?<=[a-z]{2})cao$"), "ção"),
    (re.compile(r"(?<=[a-z]{2})oes$"), "ões"),
    (re.compile(r"(?<=[a-z]{2})ao$"), "ão"),
)
_ASCII_WORD = re.compile(r"\b[A-Za-z]+\b")


def _accent_word(word: str) -> str:
    lower = word.lower()
    fixed = UNACCENTED_WORDS.get(lower)
    if fixed is None:
        for pattern, replacement in UNACCENTED_SUFFIXES:
            if pattern.search(lower):
                fixed = pattern.sub(replacement, lower)
                break
    if fixed is None:
        return word
    if word.isupper() and len(word) > 1:
        return fixed.upper()
    if word[0].isupper():
        return fixed[0].upper() + fixed[1:]
    return fixed


def restore_missing_accents(draft: ProgramDraft) -> ProgramDraft:
    """Repõe acentos quando o modelo devolve o texto inteiro sem nenhum.

    Se já há algum acento, o texto fica como veio: o modelo acentuou e uma
    palavra terminada em "ao" sem til é provavelmente de propósito.
    """
    texts = [draft.resumo, *draft.alertas]
    for block in draft.blocos:
        texts.extend(text for text in (block.titulo, block.motivo) if text)
    if any(not text.isascii() for text in texts):
        return draft

    def fix(text: str | None) -> str | None:
        if text is None:
            return None
        return _ASCII_WORD.sub(lambda match: _accent_word(match.group()), text)

    fixed = draft.model_copy(deep=True)
    fixed.resumo = fix(fixed.resumo)
    fixed.alertas = [fix(alert) for alert in fixed.alertas]
    for block in fixed.blocos:
        block.titulo = fix(block.titulo)
        block.motivo = fix(block.motivo)
    return fixed


def polish_suggested_program(draft: ProgramDraft, context: dict) -> ProgramDraft:
    """Ajustes aplicados só à resposta da IA; a edição do líder não passa aqui."""
    return adjust_program_durations(restore_missing_accents(draft), context)


def validate_and_enrich_program(draft: ProgramDraft, context: dict) -> ProgramDraft:
    catalog = {song["id"]: song for song in context["catalog"]}
    music_blocks = [
        block for block in draft.blocos if block.tipo == ProgramBlockType.MUSIC
    ]
    song_ids = [block.song_id for block in music_blocks]

    if not song_ids:
        raise ProgramValidationError("Program must contain at least one song")
    unknown_ids = sorted(song_id for song_id in song_ids if song_id not in catalog)
    if unknown_ids:
        raise ProgramValidationError(f"Unknown song_id values: {unknown_ids}")
    if len(song_ids) != len(set(song_ids)):
        raise ProgramValidationError("Program cannot repeat the same song")

    total_duration = sum(block.duracao_min for block in draft.blocos)
    target_duration = context["target_duration_minutes"]
    if abs(total_duration - target_duration) > get_duration_tolerance(target_duration):
        raise ProgramValidationError(
            f"Program duration is {total_duration}, expected {target_duration}"
        )

    enriched = draft.model_copy(deep=True)
    existing_alerts = set(enriched.alertas)
    if total_duration != target_duration:
        alert = f"A programação soma {total_duration} min; o alvo era {target_duration} min."
        if alert not in existing_alerts:
            enriched.alertas.append(alert)
            existing_alerts.add(alert)
    recent_by_song: dict[int, dict] = {}
    for usage in context["recent_song_history"]:
        recent_by_song.setdefault(usage["song_id"], usage)

    for song_id in song_ids:
        usage = recent_by_song.get(song_id)
        if usage is None:
            continue
        alert = (
            f"A música {catalog[song_id]['title']} foi usada em "
            f"{usage['event_date']}."
        )
        if alert not in existing_alerts:
            enriched.alertas.append(alert)
            existing_alerts.add(alert)

    return enriched
