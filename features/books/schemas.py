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
    image_url: Optional[str] = None


class BookUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1)
    author: Optional[str] = Field(default=None, min_length=1)
    isbn: Optional[str] = None
    description: Optional[str] = None
    published_year: Optional[int] = None
    genre: Optional[str] = None
    image_url: Optional[str] = None


class BookRead(BaseModel):
    id: int
    title: str
    author: str
    isbn: Optional[str]
    description: Optional[str]
    published_year: Optional[int]
    genre: Optional[str]
    image_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    total_copies: int
    available_copies: int
    is_checked_out: bool


class BookListPage(BaseModel):
    items: list[BookRead]
    total: int
    limit: int
    offset: int


class BookCopyCreate(BaseModel):
    barcode: Optional[str] = None


class BookCopyUpdate(BaseModel):
    barcode: Optional[str] = None


class BookCopyRead(BaseModel):
    id: int
    book_id: int
    barcode: Optional[str]
    is_checked_out: bool
    created_at: datetime
    updated_at: datetime


class BookCopyListResponse(BaseModel):
    items: list[BookCopyRead]
