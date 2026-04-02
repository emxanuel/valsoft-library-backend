from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from features.clients.schemas import ClientCheckout


class CheckoutRequest(BaseModel):
    due_at: Optional[datetime] = None
    client: ClientCheckout
    copy_id: Optional[int] = None


class LoanRead(BaseModel):
    id: int
    book_id: int
    copy_id: int
    copy_barcode: Optional[str] = None
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
    copy_id: int
    copy_barcode: Optional[str] = None
    book_title: str
    book_author: str
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    checked_out_at: datetime
    due_at: Optional[datetime] = None


class LoanHistoryRead(BaseModel):
    loan_id: int
    book_id: int
    copy_id: int
    copy_barcode: Optional[str] = None
    book_title: str
    book_author: str
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    checked_out_at: datetime
    due_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    staff_email: Optional[str] = None


class LoanHistoryPage(BaseModel):
    items: list[LoanHistoryRead]
    total: int
    limit: int
    offset: int


class AdminOpenLoanRead(BaseModel):
    loan_id: int
    book_id: int
    copy_id: int
    copy_barcode: Optional[str] = None
    book_title: str
    book_author: str
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    checked_out_at: datetime
    due_at: Optional[datetime] = None
    staff_user_id: int
    staff_email: str
    staff_first_name: str
    staff_last_name: str


class AdminOpenLoansPage(BaseModel):
    items: list[AdminOpenLoanRead]
    total: int
    limit: int
    offset: int
