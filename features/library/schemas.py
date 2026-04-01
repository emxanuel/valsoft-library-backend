from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    isbn: Optional[str] = None
    description: Optional[str] = None
    published_year: Optional[int] = None
    genre: Optional[str] = None


class BookUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    author: Optional[str] = Field(default=None, min_length=1)
    isbn: Optional[str] = None
    description: Optional[str] = None
    published_year: Optional[int] = None
    genre: Optional[str] = None


class BookRead(BaseModel):
    id: int
    title: str
    author: str
    isbn: Optional[str]
    description: Optional[str]
    published_year: Optional[int]
    genre: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_checked_out: bool


class CheckoutRequest(BaseModel):
    due_at: Optional[datetime] = None


class LoanRead(BaseModel):
    id: int
    book_id: int
    user_id: int
    checked_out_at: datetime
    due_at: Optional[datetime]
    returned_at: Optional[datetime]
