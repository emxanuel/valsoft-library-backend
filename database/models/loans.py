from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Loan(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", nullable=False)
    user_id: int = Field(foreign_key="users.id", nullable=False)
    client_id: Optional[int] = Field(default=None, foreign_key="client.id")
    checked_out_at: datetime = Field(default_factory=datetime.utcnow)
    due_at: Optional[datetime] = Field(default=None)
    returned_at: Optional[datetime] = Field(default=None)
