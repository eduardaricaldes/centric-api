from datetime import date as date_type
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.models.assignment import Assignment
from app.models.event import Event, EventStatus, EventType
from app.models.ministry import Ministry
from app.models.playlist import Playlist
from app.models.playlist_song import PlaylistSong
from app.models.preaching import Preaching
from app.models.roles import UserRole
from app.models.user import User
from app.schemas.assignment import AssignmentCreate, AssignmentResponse
from app.schemas.event import (
    EventCreate,
    EventDetailResponse,
    EventListResponse,
    EventResponse,
    EventUpdate,
)
from app.schemas.playlist import PlaylistResponse
from app.schemas.playlist_song import PlaylistSongResponse
from app.schemas.preaching import PreachingResponse, PreachingUpsert
from app.services.permissions import (
    ensure_event_collaborator,
    ensure_event_owner,
    ensure_ministry_manager,
)
from app.services.song_views import resolve_song_view, song_for_view

events_router = APIRouter(prefix="/events", tags=["Events"])


def get_event_or_404(db: Session, event_id: int) -> Event:
    event = db.query(Event).filter(Event.id == event_id).first()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return event


def get_event_warnings(assignments: list[Assignment]) -> list[dict]:
    ministries_by_user: dict[int, set[int]] = {}
    for assignment in assignments:
        ministries_by_user.setdefault(assignment.user_id, set()).add(
            assignment.ministry_id
        )

    warnings = []
    for user_id, ministry_ids in sorted(ministries_by_user.items()):
        if len(ministry_ids) > 1:
            sorted_ids = sorted(ministry_ids)
            warnings.append(
                {
                    "code": "USER_MULTIPLE_MINISTRIES",
                    "message": "User is assigned to multiple ministries in this event",
                    "user_id": user_id,
                    "ministry_ids": sorted_ids,
                }
            )
    return warnings


def serialize_playlist(playlist: Playlist, selected_view: str) -> dict:
    data = PlaylistResponse.model_validate(playlist).model_dump()
    data["songs"] = []
    for item in playlist.songs:
        item_data = PlaylistSongResponse.model_validate(item).model_dump()
        item_data["song"] = song_for_view(item.song, selected_view)
        data["songs"].append(item_data)
    return data


@events_router.post(
    "/",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.LEADER)),
):
    event = Event(**payload.model_dump(), created_by=current_user.id)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@events_router.get("/", response_model=EventListResponse)
def list_events(
    from_date: date_type | None = Query(default=None, alias="from"),
    to_date: date_type | None = Query(default=None, alias="to"),
    event_type: EventType | None = Query(default=None, alias="type"),
    event_status: EventStatus | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if from_date is not None and to_date is not None and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from must be before or equal to to",
        )

    query = db.query(Event)
    if from_date is not None:
        query = query.filter(Event.date >= from_date)
    if to_date is not None:
        query = query.filter(Event.date <= to_date)
    if event_type is not None:
        query = query.filter(Event.type == event_type)
    if event_status is not None:
        query = query.filter(Event.status == event_status)

    total = query.count()
    items = (
        query.order_by(Event.date, Event.time, Event.id)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return {"total": total, "page": page, "limit": limit, "items": items}


@events_router.get(
    "/{event_id}",
    response_model=EventDetailResponse,
    response_model_exclude_unset=True,
)
def get_event(
    event_id: int,
    view: Literal["lyrics", "chords"] | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = (
        db.query(Event)
        .options(
            selectinload(Event.assignments).selectinload(Assignment.user),
            selectinload(Event.assignments).selectinload(Assignment.ministry),
            selectinload(Event.preaching).selectinload(Preaching.preacher),
            selectinload(Event.playlist)
            .selectinload(Playlist.songs)
            .selectinload(PlaylistSong.song),
        )
        .filter(Event.id == event_id)
        .first()
    )
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    data = EventResponse.model_validate(event).model_dump()
    data["assignments"] = event.assignments
    data["preaching"] = event.preaching
    data["warnings"] = get_event_warnings(event.assignments)
    data["playlist"] = None
    if event.playlist is not None:
        selected_view = resolve_song_view(view, current_user)
        data["playlist"] = serialize_playlist(event.playlist, selected_view)
    return data


@events_router.put("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    payload: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = get_event_or_404(db, event_id)
    ensure_event_owner(db, current_user, event)

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(event, key, value)

    db.commit()
    db.refresh(event)
    return event


@events_router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = get_event_or_404(db, event_id)
    ensure_event_owner(db, current_user, event)
    db.delete(event)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@events_router.post(
    "/{event_id}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    event_id: int,
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_event_or_404(db, event_id)
    ensure_ministry_manager(db, current_user, payload.ministry_id)

    if db.query(User).filter(User.id == payload.user_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")

    if db.query(Ministry).filter(Ministry.id == payload.ministry_id).first() is None:
        raise HTTPException(status_code=404, detail="Ministry not found")

    assignment = Assignment(event_id=event_id, **payload.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@events_router.get(
    "/{event_id}/preaching",
    response_model=PreachingResponse,
)
def get_preaching(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_event_or_404(db, event_id)
    preaching = (
        db.query(Preaching)
        .options(selectinload(Preaching.preacher))
        .filter(Preaching.event_id == event_id)
        .first()
    )
    if preaching is None:
        raise HTTPException(status_code=404, detail="Preaching not found")
    return preaching


@events_router.put(
    "/{event_id}/preaching",
    response_model=PreachingResponse,
)
def upsert_preaching(
    event_id: int,
    payload: PreachingUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    event = get_event_or_404(db, event_id)
    ensure_event_collaborator(db, current_user, event)

    if db.query(User).filter(User.id == payload.preacher_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")

    preaching = db.query(Preaching).filter(Preaching.event_id == event_id).first()
    if preaching is None:
        preaching = Preaching(event_id=event_id, **payload.model_dump())
        db.add(preaching)
    else:
        for key, value in payload.model_dump().items():
            setattr(preaching, key, value)

    db.commit()
    preaching = (
        db.query(Preaching)
        .options(selectinload(Preaching.preacher))
        .filter(Preaching.event_id == event_id)
        .one()
    )
    return preaching
