from fastapi import Depends, APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.schemas.user import UserCreate, UserLogin, Token
from app.models.user import User

from app.services.auth_services import get_user_by_email, authenticate_user

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", status_code = status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    existing_user = get_user_by_email(db, payload.email)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HTTP_400_BAD_REQUEST"
        )
    user = User(
        email = payload.email,
        hashed_password = hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"mensage": "User created"} 

@router.post("/login", status_code= status.HTTP_200_OK)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user (db, payload.email, payload.password)

    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail=" email or passaword are wrong",
        )
    access_token = create_access_token(data={"sub":user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }

