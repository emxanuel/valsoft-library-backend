from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import Session

from database.models.clients import Client
from database.models.users import Users
from features.books import services as book_services
from features.books.schemas import (
    BookCreate,
    BookListPage,
    BookRead,
    BookUpdate,
)
from features.loans import services as loan_services
from features.loans.schemas import CheckoutRequest, LoanRead


def _loan_client_fields(client: Client | None) -> tuple[
    int | None,
    str | None,
    str | None,
    str | None,
]:
    if client is None or client.id is None:
        return None, None, None, None
    return (
        client.id,
        client.name,
        client.email,
        client.phone,
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
        is_out = loan_services.book_has_open_loan(session, bid)
    return BookRead(
        id=bid,
        title=book.title,
        author=book.author,
        isbn=book.isbn,
        description=book.description,
        published_year=book.published_year,
        genre=book.genre,
        image_url=book.image_url,
        created_at=book.created_at,
        updated_at=book.updated_at,
        is_checked_out=is_out,
    )


def list_books_controller(
    session: Session,
    *,
    q: Optional[str] = None,
    genre: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> BookListPage:
    books, total = book_services.list_books(
        session,
        q=q,
        genre=genre,
        offset=offset,
        limit=limit,
    )
    ids = [b.id for b in books if b.id is not None]
    open_ids = loan_services.book_ids_with_open_loans(session, ids)
    items = [_to_book_read(session, b, open_book_ids=open_ids) for b in books]
    return BookListPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_book_controller(session: Session, book_id: int) -> BookRead:
    book = book_services.get_book_by_id(session, book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )
    return _to_book_read(session, book)


def create_book_controller(payload: BookCreate, session: Session) -> BookRead:
    book = book_services.create_book(
        session,
        title=payload.title,
        author=payload.author,
        isbn=payload.isbn,
        description=payload.description,
        published_year=payload.published_year,
        genre=payload.genre,
        image_url=payload.image_url,
    )
    return _to_book_read(session, book)


def update_book_controller(
    book_id: int,
    payload: BookUpdate,
    session: Session,
) -> BookRead:
    book = book_services.get_book_by_id(session, book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )
    data = payload.model_dump(exclude_unset=True)
    book = book_services.update_book(session, book, **data)
    return _to_book_read(session, book)


def delete_book_controller(book_id: int, session: Session) -> None:
    book = book_services.get_book_by_id(session, book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )
    try:
        book_services.delete_book(session, book)
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
        loan, patron = loan_services.checkout_book(
            session,
            book_id=book_id,
            user_id=current_user.id,  # type: ignore[arg-type]
            client_name=payload.client.name,
            client_email=payload.client.email,
            client_phone=payload.client.phone,
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
    lid = loan.id
    bid = loan.book_id
    uid = loan.user_id
    if lid is None or bid is None or uid is None:
        raise RuntimeError("loan ids missing after persist")
    cid, cname, cemail, cphone = _loan_client_fields(patron)
    return LoanRead(
        id=lid,
        book_id=bid,
        user_id=uid,
        client_id=cid,
        client_name=cname,
        client_email=cemail,
        client_phone=cphone,
        checked_out_at=loan.checked_out_at,
        due_at=loan.due_at,
        returned_at=loan.returned_at,
    )


def checkin_controller(
    book_id: int,
    current_user: Users,
    session: Session,
) -> LoanRead:
    try:
        loan = loan_services.checkin_book(
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
    patron = session.get(Client, loan.client_id) if loan.client_id else None
    lid = loan.id
    bid = loan.book_id
    uid = loan.user_id
    if lid is None or bid is None or uid is None:
        raise RuntimeError("loan ids missing after persist")
    cid, cname, cemail, cphone = _loan_client_fields(patron)
    return LoanRead(
        id=lid,
        book_id=bid,
        user_id=uid,
        client_id=cid,
        client_name=cname,
        client_email=cemail,
        client_phone=cphone,
        checked_out_at=loan.checked_out_at,
        due_at=loan.due_at,
        returned_at=loan.returned_at,
    )
