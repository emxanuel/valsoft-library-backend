from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import Session

from database.models.users import Users
from features.library import services as library_services
from features.library.schemas import (
    BookCreate,
    BookRead,
    BookUpdate,
    CheckoutRequest,
    LoanRead,
    MyOpenLoanRead,
)


def _to_book_read(
    session: Session,
    book,
    *,
    open_book_ids: Optional[set[int]] = None,
) -> BookRead:
    bid = book.id
    if bid is None:
        raise RuntimeError("book id missing after persist")
    if open_book_ids is not None:
        is_out = bid in open_book_ids
    else:
        is_out = library_services.book_has_open_loan(session, bid)
    return BookRead(
        id=bid,
        title=book.title,
        author=book.author,
        isbn=book.isbn,
        description=book.description,
        published_year=book.published_year,
        genre=book.genre,
        created_at=book.created_at,
        updated_at=book.updated_at,
        is_checked_out=is_out,
    )


def list_my_loans_controller(
    session: Session,
    current_user: Users,
) -> list[MyOpenLoanRead]:
    rows = library_services.list_open_loans_for_user(
        session,
        current_user.id,  # type: ignore[arg-type]
    )
    result: list[MyOpenLoanRead] = []
    for loan, book in rows:
        lid = loan.id
        bid = book.id
        if lid is None or bid is None:
            raise RuntimeError("loan or book id missing after persist")
        result.append(
            MyOpenLoanRead(
                loan_id=lid,
                book_id=bid,
                book_title=book.title,
                book_author=book.author,
                checked_out_at=loan.checked_out_at,
                due_at=loan.due_at,
            )
        )
    return result


def list_books_controller(
    session: Session,
    *,
    q: Optional[str] = None,
    genre: Optional[str] = None,
) -> list[BookRead]:
    books = library_services.list_books(session, q=q, genre=genre)
    ids = [b.id for b in books if b.id is not None]
    open_ids = library_services.book_ids_with_open_loans(session, ids)
    return [_to_book_read(session, b, open_book_ids=open_ids) for b in books]


def get_book_controller(session: Session, book_id: int) -> BookRead:
    book = library_services.get_book_by_id(session, book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )
    return _to_book_read(session, book)


def create_book_controller(payload: BookCreate, session: Session) -> BookRead:
    book = library_services.create_book(
        session,
        title=payload.title,
        author=payload.author,
        isbn=payload.isbn,
        description=payload.description,
        published_year=payload.published_year,
        genre=payload.genre,
    )
    return _to_book_read(session, book)


def update_book_controller(
    book_id: int,
    payload: BookUpdate,
    session: Session,
) -> BookRead:
    book = library_services.get_book_by_id(session, book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )
    data = payload.model_dump(exclude_unset=True)
    book = library_services.update_book(session, book, **data)
    return _to_book_read(session, book)


def delete_book_controller(book_id: int, session: Session) -> None:
    book = library_services.get_book_by_id(session, book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )
    try:
        library_services.delete_book(session, book)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def checkout_controller(
    book_id: int,
    payload: CheckoutRequest,
    current_user: Users,
    session: Session,
) -> LoanRead:
    try:
        loan = library_services.checkout_book(
            session,
            book_id=book_id,
            user_id=current_user.id,  # type: ignore[arg-type]
            due_at=payload.due_at,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "Book not found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=detail,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc
    return LoanRead.model_validate(loan, from_attributes=True)


def checkin_controller(
    book_id: int,
    current_user: Users,
    session: Session,
) -> LoanRead:
    try:
        loan = library_services.checkin_book(
            session,
            book_id=book_id,
            acting_user_id=current_user.id,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "No active loan for this book":
            st = status.HTTP_404_NOT_FOUND
        elif detail == "Only the borrower can check in this book":
            st = status.HTTP_403_FORBIDDEN
        else:
            st = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=st, detail=detail) from exc
    return LoanRead.model_validate(loan, from_attributes=True)
