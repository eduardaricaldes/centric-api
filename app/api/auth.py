from fastapi import Depends, APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password
from app.models.roles import UserRole
from app.models.user import User
from app.schemas.user import Token, UserCreate, UserResponse, UserUpdate

from app.services.auth_services import get_user_by_email, authenticate_user

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
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
        role=UserRole.MEMBER,
        prefers_chords=payload.prefers_chords,
    )
    db.add(user)
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
    current_user.prefers_chords = payload.prefers_chords
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
def login(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user (db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    access_token = create_access_token(
    data={
        "sub": user.email,
        "role": user.role.value,
    }
)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role.value,
    }
