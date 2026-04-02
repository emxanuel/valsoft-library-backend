from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


# Persist lowercase values ("admin", "employee") as VARCHAR. Using native_enum=False
# avoids PostgreSQL ENUM types whose labels (ADMIN/EMPLOYEE) mismatch DB strings.
_user_role_enum = SAEnum(
    UserRole,
    name="user_role_str",
    native_enum=False,
    length=20,
    values_callable=lambda obj: [m.value for m in obj],
)


class Users(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: str = Field(index=True, nullable=False)
    last_name: str = Field(index=True, nullable=False)
    email: str = Field(index=True, nullable=False, unique=True)
    password_hash: str = Field(nullable=False)
    role: UserRole = Field(
        default=UserRole.EMPLOYEE,
        sa_column=Column(
            "role",
            _user_role_enum,
            nullable=False,
            server_default="employee",
            index=True,
        ),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
