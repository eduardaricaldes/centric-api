# from fastapi import Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordBearer
# from jose import JWTError, jwt
# from sqlalchemy.orm import Session

# from app.core.config import settings
# from app.core.database import get_db
# from app.models.user import User

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
# #oauth2_scheme pega o toke do header da requisicao 
# def get_current_user(
#         token: str = Depends(oauth2_scheme), # token é uma variavel do tipo str e o valor dela e obtido pela dependencia oauth2_scheme
#         db: Session = Depends(get_db),

# ) -> User:
#     credentials_exeception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED
#         detail=" couldn't validate credentials ",
#         headers={"WWW-Authenicate":"Bearer"},
#     )
#     try:
#         payload = jwt.decode(
#             token,
#             settings.secret_key,
#             algorithms=[settings.algorithm],
#             )
        
#         email: str|None = payload.get("sub")
#         if email is None:
#             raise credentials_exeception
        
#         user =  db.query(User).filter(User.email == email).first()

        
#     except JWTError:
#         raise credentials_exeception
    
#     return user 