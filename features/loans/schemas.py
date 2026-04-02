from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from features.clients.schemas import ClientCheckout


class CheckoutRequest(BaseModel):
    due_at: Optional[datetime] = None
    client: ClientCheckout


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
