from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class AuthSession(SQLModel, table=True):
    __tablename__ = "auth_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(nullable=False, unique=True, index=True)
    user_id: int = Field(foreign_key="users.id", nullable=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
