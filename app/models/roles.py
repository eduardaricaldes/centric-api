from enum import StrEnum

from sqlalchemy import Enum as SQLAlchemyEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    LEADER = "LEADER"
    MEMBER = "MEMBER"


class MinistryRole(StrEnum):
    LEADER = "LEADER"
    MEMBER = "MEMBER"


class InviteKind(StrEnum):
    INVITE = "INVITE"
    PASSWORD_RESET = "PASSWORD_RESET"


user_role_type = SQLAlchemyEnum(
    UserRole,
    name="user_role",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    length=6,
)

ministry_role_type = SQLAlchemyEnum(
    MinistryRole,
    name="ministry_role",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    length=6,
)

invite_kind_type = SQLAlchemyEnum(
    InviteKind,
    name="invite_kind",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
    length=20,
)
