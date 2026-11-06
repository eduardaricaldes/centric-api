import getpass
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.security import hash_password
from app.models.roles import UserRole
from app.models.user import User

ADMIN_EMAIL = (os.environ.get("ADMIN_EMAIL") or input("E-mail do admin: ")).strip().lower()
ADMIN_NAME = os.environ.get("ADMIN_NAME") or input("Nome do admin: ").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Senha do admin: ")

if not all([ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME]):
    print("Error: e-mail, nome e senha são obrigatórios.")
    sys.exit(1)
try:
    # A API valida o e-mail ao responder: um inválido aqui trancaria o admin para fora.
    validate_email(ADMIN_EMAIL, check_deliverability=False)
except EmailNotValidError as exc:
    print(f"Error: e-mail inválido: {exc}")
    sys.exit(1)
if len(ADMIN_PASSWORD) < 8:
    print("Error: a senha precisa ter pelo menos 8 caracteres.")
    sys.exit(1)

with Session(engine) as db:
    existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
    if existing:
        print(f"User {ADMIN_EMAIL} already exists (role={existing.role}). Nothing to do.")
        sys.exit(0)

    admin = User(
        name=ADMIN_NAME,
        email=ADMIN_EMAIL,
        password_hash=hash_password(ADMIN_PASSWORD),
        role=UserRole.ADMIN,
    )
    db.add(admin)
    db.commit()
    print(f"Admin user {ADMIN_EMAIL} created successfully.")
