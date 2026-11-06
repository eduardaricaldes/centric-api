from fastapi import Depends, APIRouter, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.models.invite import InviteKind
from app.models.ministry_member import MinistryMember
from app.models.roles import MinistryRole, UserRole
from app.models.user import User
from app.schemas.password import ChangePasswordRequest, ResetPasswordRequest
from app.schemas.user import Token, UserCreate, UserResponse, UserUpdate

from app.services.auth_services import get_user_by_email, authenticate_user
from app.services.invites import get_invite_by_token, utcnow
from app.services.memberships import sync_global_role

router = APIRouter(prefix="/auth", tags=["Auth"])


def issue_token(user: User) -> dict:
    access_token = create_access_token(
        data={
            "sub": user.email,
            "role": user.role.value,
            "ver": user.token_version,
        }
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role.value,
    }


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    if not payload.invite_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite token is required",
        )

    invite = get_invite_by_token(db, payload.invite_token)
    if invite is None or invite.kind != InviteKind.INVITE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid invite token",
        )
    if invite.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite already used",
        )
    if invite.expires_at < utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite expired",
        )
    if invite.email is not None and invite.email.lower() != payload.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invite does not match this email",
        )

    existing_user = get_user_by_email(db, payload.email)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail already registered"
        )
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=invite.role or UserRole.MEMBER,
        prefers_chords=payload.prefers_chords,
    )
    db.add(user)
    db.flush()

    if invite.ministry_id is not None:
        db.add(
            MinistryMember(
                ministry_id=invite.ministry_id,
                user_id=user.id,
                role=invite.ministry_role or MinistryRole.MEMBER,
                instrument=invite.instrument,
            )
        )
        db.flush()

    sync_global_role(db, user)

    invite.used_at = utcnow()
    invite.used_by = user.id

    db.commit()
    db.refresh(user)

    return user


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(current_user, key, value)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/change-password", response_model=Token)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.password_hash = hash_password(payload.new_password)
    current_user.token_version += 1
    db.commit()
    return issue_token(current_user)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    invite = get_invite_by_token(db, payload.token)
    if invite is None or invite.kind != InviteKind.PASSWORD_RESET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid reset token",
        )
    if invite.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reset token already used",
        )
    if invite.expires_at < utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reset token expired",
        )

    user = db.query(User).filter(User.email == invite.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    invite.used_at = utcnow()
    invite.used_by = user.id
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
def login(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    user = authenticate_user (db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return issue_token(user)
