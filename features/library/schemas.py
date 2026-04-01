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
    is_checked_out: bool


class BookListPage(BaseModel):
    items: list[BookRead]
    total: int
    limit: int
    offset: int


class ClientCheckout(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    phone: Optional[str] = None


class CheckoutRequest(BaseModel):
    due_at: Optional[datetime] = None
    client: ClientCheckout


class ClientRead(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    created_at: datetime
    updated_at: datetime


class ClientListPage(BaseModel):
    items: list[ClientRead]
    total: int
    limit: int
    offset: int


class LoanRead(BaseModel):
    id: int
    book_id: int
    user_id: int
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    checked_out_at: datetime
    due_at: Optional[datetime]
    returned_at: Optional[datetime]


class MyOpenLoanRead(BaseModel):
    loan_id: int
    book_id: int
    book_title: str
    book_author: str
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    checked_out_at: datetime
    due_at: Optional[datetime] = None
