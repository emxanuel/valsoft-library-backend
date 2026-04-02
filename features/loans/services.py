from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, col, select

from database.models.books import Book
from database.models.clients import Client
from database.models.loans import Loan
from features.clients import services as client_services


def book_ids_with_open_loans(session: Session, book_ids: list[int]) -> set[int]:
    if not book_ids:
        return set()
    stmt = (
        select(Loan.book_id)
        .where(col(Loan.book_id).in_(book_ids))
        .where(col(Loan.returned_at).is_(None))
    )
    return set(session.exec(stmt).all())


def book_has_open_loan(session: Session, book_id: int) -> bool:
    stmt = (
        select(Loan.id)
        .where(Loan.book_id == book_id)
        .where(col(Loan.returned_at).is_(None))
        .limit(1)
    )
    return session.exec(stmt).first() is not None


def get_open_loan_for_book(session: Session, book_id: int) -> Optional[Loan]:
    stmt = (
        select(Loan)
        .where(Loan.book_id == book_id)
        .where(col(Loan.returned_at).is_(None))
        .limit(1)
    )
    return session.exec(stmt).first()


def list_open_loans_for_user(
    session: Session, user_id: int
) -> list[tuple[Loan, Book, Optional[Client]]]:
    stmt = (
        select(Loan, Book, Client)
        .join(Book, Loan.book_id == Book.id)  # type: ignore[arg-type]
        .outerjoin(Client, Loan.client_id == Client.id)  # type: ignore[arg-type]
        .where(Loan.user_id == user_id)
        .where(col(Loan.returned_at).is_(None))
        .where(col(Book.deleted_at).is_(None))
        .order_by(col(Loan.checked_out_at).desc())
    )
    return list(session.exec(stmt).all())


def checkout_book(
    session: Session,
    *,
    book_id: int,
    user_id: int,
    client_name: str,
    client_email: str,
    client_phone: Optional[str] = None,
    due_at: Optional[datetime] = None,
) -> tuple[Loan, Client]:
    book = session.get(Book, book_id)
    if book is None or book.deleted_at is not None:
        msg = "Book not found"
        raise ValueError(msg)
    if book_has_open_loan(session, book_id):
        msg = "Book is already checked out"
        raise ValueError(msg)
    client = client_services.get_or_create_client(
        session,
        name=client_name,
        email=client_email,
        phone=client_phone,
    )
    loan = Loan(
        book_id=book_id,
        user_id=user_id,
        client_id=client.id,
        due_at=due_at,
        returned_at=None,
    )
    session.add(loan)
    session.commit()
    session.refresh(loan)
    return loan, client


def checkin_book(
    session: Session,
    *,
    book_id: int,
    acting_user_id: int,
) -> Loan:
    loan = get_open_loan_for_book(session, book_id)
    if loan is None:
        msg = "No active loan for this book"
        raise ValueError(msg)
    if loan.user_id != acting_user_id:
        msg = "Only the borrower can check in this book"
        raise ValueError(msg)
    loan.returned_at = datetime.utcnow()
    session.add(loan)
    session.commit()
    session.refresh(loan)
    return loan
