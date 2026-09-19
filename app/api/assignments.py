from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.assignment import Assignment, AssignmentStatus
from app.models.event import Event
from app.models.ministry import Ministry
from app.models.user import User
from app.schemas.assignment import (
    AssignmentRespond,
    AssignmentResponse,
    AssignmentUpdate,
    MyAssignmentResponse,
)
from app.services.permissions import ensure_ministry_manager

assignments_router = APIRouter(tags=["Assignments"])


def get_assignment_or_404(db: Session, assignment_id: int) -> Assignment:
    assignment = (
        db.query(Assignment).filter(Assignment.id == assignment_id).first()
    )
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return assignment


@assignments_router.patch(
    "/assignments/{assignment_id}",
    response_model=AssignmentResponse,
)
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = get_assignment_or_404(db, assignment_id)
    ensure_ministry_manager(db, current_user, assignment.ministry_id)

    update_data = payload.model_dump(exclude_unset=True)
    new_ministry_id = update_data.get("ministry_id")
    if new_ministry_id is not None:
        ensure_ministry_manager(db, current_user, new_ministry_id)
        if db.query(Ministry).filter(Ministry.id == new_ministry_id).first() is None:
            raise HTTPException(status_code=404, detail="Ministry not found")

    new_user_id = update_data.get("user_id")
    if new_user_id is not None:
        if db.query(User).filter(User.id == new_user_id).first() is None:
            raise HTTPException(status_code=404, detail="User not found")
        if new_user_id != assignment.user_id:
            assignment.status = AssignmentStatus.INVITED
            assignment.responded_at = None

    for key, value in update_data.items():
        setattr(assignment, key, value)

    db.commit()
    db.refresh(assignment)
    return assignment


@assignments_router.delete(
    "/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = get_assignment_or_404(db, assignment_id)
    ensure_ministry_manager(db, current_user, assignment.ministry_id)
    db.delete(assignment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@assignments_router.post(
    "/assignments/{assignment_id}/respond",
    response_model=AssignmentResponse,
)
def respond_to_assignment(
    assignment_id: int,
    payload: AssignmentRespond,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = get_assignment_or_404(db, assignment_id)
    if assignment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned user can respond",
        )

    assignment.status = payload.status
    assignment.responded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assignment)
    return assignment


@assignments_router.get(
    "/me/assignments",
    response_model=list[MyAssignmentResponse],
)
def list_my_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Assignment, Event)
        .join(Event, Event.id == Assignment.event_id)
        .filter(Assignment.user_id == current_user.id)
        .order_by(Event.date, Event.time, Assignment.id)
        .all()
    )

    result = []
    for assignment, event in rows:
        data = AssignmentResponse.model_validate(assignment).model_dump()
        data.update(
            event_title=event.title,
            event_date=event.date,
            event_time=event.time,
        )
        result.append(data)
    return result
