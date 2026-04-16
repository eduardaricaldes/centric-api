from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.user import User 

def get_user_by_email(db: Session, email:str) -> bool:
    return db.query(User).filter(User.email == email).first()

def login(db:Session, email:str, password:str) -> User|None:
    user = get_user_by_email(db,email)
    if not user:
       return None
    if verify_password(password,user.hashed_password):
        return user
    return None
