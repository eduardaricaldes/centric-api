"""Celular segue o telão ao vivo (Fase 4).

O operador manda o slide atual (PUT). O celular, com o link público do evento,
lê o slide atual: por WebSocket quando o servidor aguenta conexão aberta (VPS),
ou perguntando a cada poucos segundos (GET) quando não aguenta (Vercel). Se a
internet cair, o celular fica no último slide recebido; o telão não depende
disto.
"""

import asyncio
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.models.event import Event
from app.models.live_state import LiveState
from app.models.share_link import ShareLink, ShareLinkKind
from app.models.user import User
from app.schemas.live import LiveStateResponse, LiveUpdate
from app.services.permissions import ensure_event_collaborator

live_router = APIRouter(tags=["Live"])

# O WebSocket fica aberto o culto inteiro: abre uma sessão do banco só para a
# leitura inicial, em vez de segurar uma conexão do pool por celular. Os testes
# trocam esta fábrica pela do banco de teste.
session_factory = SessionLocal


class LiveHub:
    """Conexões abertas por evento, no mesmo processo."""

    def __init__(self) -> None:
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def broadcast(self, event_id: int, payload: dict) -> None:
        message = json.dumps(payload, default=str)
        for socket in list(self.connections.get(event_id, ())):
            try:
                await socket.send_text(message)
            except Exception:  # noqa: BLE001 - conexão caída sai da lista
                self.connections[event_id].discard(socket)


hub = LiveHub()


def to_response(state: LiveState | None) -> LiveStateResponse:
    if state is None:
        return LiveStateResponse(mode="logo", version=0)
    return LiveStateResponse(
        mode=state.mode,
        song_index=state.song_index,
        slide_index=state.slide_index,
        song_title=state.song_title,
        lines=state.lines.split("\n") if state.lines else [],
        version=state.version,
        updated_at=state.updated_at,
    )


def event_from_share_token(db: Session, token: str) -> Event:
    # Importado aqui para não criar ciclo com share_links (que também é público).
    from app.api.share_links import CHURCH_TZ, event_link_expires_on
    from app.services.invites import utcnow

    link = (
        db.query(ShareLink)
        .filter(ShareLink.token == token, ShareLink.revoked_at.is_(None))
        .first()
    )
    if link is None or link.kind != ShareLinkKind.EVENT:
        raise HTTPException(status_code=404, detail="Link not found")
    expires_on = event_link_expires_on(link.event)
    if expires_on is not None and utcnow().astimezone(CHURCH_TZ).date() > expires_on:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Link expired")
    return link.event


@live_router.put("/events/{event_id}/live", response_model=LiveStateResponse)
async def update_live(
    event_id: int,
    payload: LiveUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    ensure_event_collaborator(db, current_user, event)

    state = db.query(LiveState).filter(LiveState.event_id == event_id).first()
    if state is None:
        state = LiveState(event_id=event_id, version=0)
        db.add(state)
    state.mode = payload.mode
    state.song_index = payload.song_index
    state.slide_index = payload.slide_index
    state.song_title = payload.song_title
    state.lines = "\n".join(line[:500] for line in payload.lines) if payload.mode == "slide" else None
    state.version = (state.version or 0) + 1
    db.commit()
    db.refresh(state)

    response = to_response(state)
    await hub.broadcast(event_id, response.model_dump(mode="json"))
    return response


@live_router.get("/public/live/{token}", response_model=LiveStateResponse)
@limiter.limit("120/minute")
def read_live(
    request: Request,
    response: Response,
    token: str = Path(min_length=16, max_length=64),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    event = event_from_share_token(db, token)
    state = db.query(LiveState).filter(LiveState.event_id == event.id).first()
    return to_response(state)


@live_router.websocket("/public/live/{token}/ws")
async def live_socket(websocket: WebSocket, token: str):
    db = session_factory()
    try:
        try:
            event = event_from_share_token(db, token)
        except HTTPException:
            await websocket.close(code=4404)
            return
        event_id = event.id
        state = db.query(LiveState).filter(LiveState.event_id == event_id).first()
        initial = to_response(state).model_dump(mode="json")
    finally:
        db.close()

    await websocket.accept()
    hub.connections[event_id].add(websocket)
    try:
        await websocket.send_text(json.dumps(initial, default=str))
        while True:
            # O celular não manda nada; isto só segura a conexão aberta.
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=60)
            except asyncio.TimeoutError:
                await websocket.send_text('{"ping":true}')
    except WebSocketDisconnect:
        pass
    finally:
        hub.connections[event_id].discard(websocket)
