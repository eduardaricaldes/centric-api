from datetime import datetime, timedelta, timezone

from jose import jwt 
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated = "auto") # -> ferramenta que cria senha 

def hash_password(password:str) -> str:
    return pwd_context.hash(password) #-> funcao definida para fazer o password ser do tipo str e quando retornar ser criptografado 

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password) # -> funcao criada para verificar se a senha criada e igual a senha criptografada e que deve retornar true ou false

def create_access_token(data:dict) -> str:
    to_enconde = data.copy() # -> funcao de criar o token 
    expire = datetime.now(timezone.utc)+timedelta(minutes=settings.access_token_expire_minutes) # -> expiracao 
    to_enconde.update({"exp":expire}) # -> add o payload 
    return jwt.encode(
        to_enconde,
        settings.secret_key,
        algorithm = settings.algorithm,
    )
    # .copy() a cópia e o seu objeto de usuário original permanece "limpo" para ser usado em outras partes do código.
