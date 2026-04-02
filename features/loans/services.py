from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, col, select

from database.models.book_copies import BookCopy
from database.models.books import Book
from database.models.clients import Client
from database.models.loans import Loan
from database.models.users import Users
from features.books import copy_services
from features.clients import services as client_services


def copy_ids_with_open_loans(session: Session, copy_ids: list[int]) -> set[int]:
    return copy_services.copy_ids_with_open_loans(session, copy_ids)


def copy_has_open_loan(session: Session, copy_id: int) -> bool:
    return copy_services.copy_has_open_loan(session, copy_id)


def get_open_loan_for_copy(session: Session, copy_id: int) -> Optional[Loan]:
    stmt = (
        select(Loan)
        .where(Loan.copy_id == copy_id)
        .where(col(Loan.returned_at).is_(None))
        .limit(1)
    )
    return session.exec(stmt).first()


def get_open_loan_by_id(session: Session, loan_id: int) -> Optional[Loan]:
    stmt = (
        select(Loan)
        .where(Loan.id == loan_id)
        .where(col(Loan.returned_at).is_(None))
        .limit(1)
    )
    return session.exec(stmt).first()


def list_open_loans_for_user(
    session: Session, user_id: int
) -> list[tuple[Loan, BookCopy, Book, Optional[Client]]]:
    stmt = (
        select(Loan, BookCopy, Book, Client)
        .join(BookCopy, Loan.copy_id == BookCopy.id)  # type: ignore[arg-type]
        .join(Book, BookCopy.book_id == Book.id)  # type: ignore[arg-type]
        .outerjoin(Client, Loan.client_id == Client.id)  # type: ignore[arg-type]
        .where(Loan.user_id == user_id)
        .where(col(Loan.returned_at).is_(None))
        .where(col(Book.deleted_at).is_(None))
        .where(col(BookCopy.deleted_at).is_(None))
        .order_by(col(Loan.checked_out_at).desc())
    )
    return list(session.exec(stmt).all())


def list_all_open_loans_paginated(
    session: Session,
    *,
    offset: int,
    limit: int,
) -> tuple[list[tuple[Loan, BookCopy, Book, Optional[Client], Users]], int]:
    """All open loans across staff; non-deleted books/copies only."""
    count_stmt = (
        select(func.count())
        .select_from(Loan)
        .join(BookCopy, Loan.copy_id == BookCopy.id)  # type: ignore[arg-type]
        .join(Book, BookCopy.book_id == Book.id)  # type: ignore[arg-type]
        .join(Users, Loan.user_id == Users.id)  # type: ignore[arg-type]
        .where(col(Loan.returned_at).is_(None))
        .where(col(Book.deleted_at).is_(None))
        .where(col(BookCopy.deleted_at).is_(None))
    )
    total = int(session.exec(count_stmt).one())
    stmt = (
        select(Loan, BookCopy, Book, Client, Users)  # type: ignore[call-overload]
        .join(BookCopy, Loan.copy_id == BookCopy.id)  # type: ignore[arg-type]
        .join(Book, BookCopy.book_id == Book.id)  # type: ignore[arg-type]
        .outerjoin(Client, Loan.client_id == Client.id)  # type: ignore[arg-type]
        .join(Users, Loan.user_id == Users.id)  # type: ignore[arg-type]
        .where(col(Loan.returned_at).is_(None))
        .where(col(Book.deleted_at).is_(None))
        .where(col(BookCopy.deleted_at).is_(None))
        .order_by(col(Loan.checked_out_at).desc())
        .offset(offset)
        .limit(limit)
    )
    rows = list(session.exec(stmt).all())
    return rows, total


def list_staff_loan_history_paginated(
    session: Session,
    *,
    user_id: int,
    offset: int,
    limit: int,
) -> tuple[list[tuple[Loan, BookCopy, Book, Optional[Client]]], int]:
    """Past returns for the current staff member; includes soft-deleted books/copies."""
    base_join = (
        select(Loan, BookCopy, Book, Client)
        .join(BookCopy, Loan.copy_id == BookCopy.id)  # type: ignore[arg-type]
        .join(Book, BookCopy.book_id == Book.id)  # type: ignore[arg-type]
        .outerjoin(Client, Loan.client_id == Client.id)  # type: ignore[arg-type]
        .where(Loan.user_id == user_id)
        .where(col(Loan.returned_at).is_not(None))
    )
    count_stmt = (
        select(func.count())
        .select_from(Loan)
        .join(BookCopy, Loan.copy_id == BookCopy.id)  # type: ignore[arg-type]
        .join(Book, BookCopy.book_id == Book.id)  # type: ignore[arg-type]
        .where(Loan.user_id == user_id)
        .where(col(Loan.returned_at).is_not(None))
    )
    total = int(session.exec(count_stmt).one())
    stmt = (
        base_join.order_by(col(Loan.returned_at).desc()).offset(offset).limit(limit)
    )
    rows = list(session.exec(stmt).all())
    return rows, total  # type: ignore[return-value]


def list_client_loan_history_paginated(
    session: Session,
    *,
    client_id: int,
    offset: int,
    limit: int,
) -> tuple[list[tuple[Loan, BookCopy, Book, Optional[Client], Users]], int]:
    """All open and returned loans for a patron (any staff); includes soft-deleted books."""
    count_stmt = (
        select(func.count())
        .select_from(Loan)
        .join(BookCopy, Loan.copy_id == BookCopy.id)  # type: ignore[arg-type]
        .join(Book, BookCopy.book_id == Book.id)  # type: ignore[arg-type]
        .where(Loan.client_id == client_id)
    )
    total = int(session.exec(count_stmt).one())
    stmt = (
        select(Loan, BookCopy, Book, Client, Users)  # type: ignore[call-overload]
        .join(BookCopy, Loan.copy_id == BookCopy.id)  # type: ignore[arg-type]
        .join(Book, BookCopy.book_id == Book.id)  # type: ignore[arg-type]
        .outerjoin(Client, Loan.client_id == Client.id)  # type: ignore[arg-type]
        .join(Users, Loan.user_id == Users.id)  # type: ignore[arg-type]
        .where(Loan.client_id == client_id)
        .order_by(col(Loan.checked_out_at).desc())
        .offset(offset)
        .limit(limit)
    )
    rows = list(session.exec(stmt).all())
    return rows, total


def checkout_book(
    session: Session,
    *,
    book_id: int,
    user_id: int,
    client_name: str,
    client_email: str,
    client_phone: Optional[str] = None,
    due_at: Optional[datetime] = None,
    copy_id: Optional[int] = None,
) -> tuple[Loan, Client]:
    book = session.get(Book, book_id)
    if book is None or book.deleted_at is not None:
        msg = "Book not found"
        raise ValueError(msg)

    resolved_copy_id: Optional[int]
    if copy_id is not None:
        bc = copy_services.get_copy_by_id(session, copy_id)
        if bc is None or bc.book_id != book_id:
            msg = "Copy not found for this book"
            raise ValueError(msg)
        if copy_services.copy_has_open_loan(session, copy_id):
            msg = "Copy is already checked out"
            raise ValueError(msg)
        resolved_copy_id = copy_id
    else:
        resolved_copy_id = copy_services.find_first_available_copy_id(session, book_id)
        if resolved_copy_id is None:
            msg = "No copies available to check out"
            raise ValueError(msg)

    client = client_services.get_or_create_client(
        session,
        name=client_name,
        email=client_email,
        phone=client_phone,
    )
    loan = Loan(
        copy_id=resolved_copy_id,
        user_id=user_id,
        client_id=client.id,
        due_at=due_at,
        returned_at=None,
    )
    session.add(loan)
    session.commit()
    session.refresh(loan)
    return loan, client


def checkin_loan(
    session: Session,
    *,
    loan_id: int,
    acting_user_id: int,
) -> Loan:
    loan = get_open_loan_by_id(session, loan_id)
    if loan is None:
        msg = "No active loan for this id"
        raise ValueError(msg)
    if loan.user_id != acting_user_id:
        msg = "Only the borrower can check in this loan"
        raise ValueError(msg)
    loan.returned_at = datetime.utcnow()
    session.add(loan)
    session.commit()
    session.refresh(loan)
    return loan
