from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True, nullable=False)
    author: str = Field(index=True, nullable=False)
    isbn: Optional[str] = Field(default=None, index=True)
    description: Optional[str] = Field(default=None)
    published_year: Optional[int] = Field(default=None)
    genre: Optional[str] = Field(default=None, index=True)
    image_url: Optional[str] = Field(default=None)
    deleted_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
