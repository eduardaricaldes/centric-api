import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.security import hash_password
from app.models.roles import UserRole
from app.models.user import User

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
ADMIN_NAME = os.environ.get("ADMIN_NAME")

if not all([ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME]):
    print("Error: ADMIN_EMAIL, ADMIN_PASSWORD and ADMIN_NAME must be set.")
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
