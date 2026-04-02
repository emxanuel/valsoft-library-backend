from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from database.models.book_copies import BookCopy
from database.models.users import Users
from features.books import copy_services
from features.books import services as book_services
from features.books.schemas import (
    BookCopyCreate,
    BookCopyListResponse,
    BookCopyRead,
    BookCopyUpdate,
    BookCreate,
    BookListPage,
    BookRead,
    BookUpdate,
)
from features.loans import services as loan_services
from features.loans.controllers import loan_to_read
from features.loans.schemas import CheckoutRequest, LoanRead


def _to_book_read(
    session: Session,
    book,
    *,
    copy_stats: Optional[tuple[int, int]] = None,
) -> BookRead:
    if book.id is None:
        raise RuntimeError("book id missing after persist")
    book_id = book.id
    if copy_stats is not None:
        total, available = copy_stats
    else:
        total = copy_services.count_total_copies(session, book_id)
        available = copy_services.available_copies_count(session, book_id)
    is_out = available == 0 and total > 0
    return BookRead(
        id=book_id,
        title=book.title,
        author=book.author,
        isbn=book.isbn,
        description=book.description,
        published_year=book.published_year,
        genre=book.genre,
        image_url=book.image_url,
        created_at=book.created_at,
        updated_at=book.updated_at,
        total_copies=total,
        available_copies=available,
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
    stats_by_book = copy_services.copy_stats_for_book_ids(session, ids)
    items = [
        _to_book_read(
            session,
            b,
            copy_stats=stats_by_book.get(b.id, (0, 0)),  # type: ignore[arg-type]
        )
        for b in books
    ]
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


def list_copies_controller(session: Session, book_id: int) -> BookCopyListResponse:
    book = book_services.get_book_by_id(session, book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )
    copies = copy_services.list_copies_for_book(session, book_id)
    ids = [c.id for c in copies if c.id is not None]
    busy = copy_services.copy_ids_with_open_loans(session, ids)
    items: list[BookCopyRead] = []
    for c in copies:
        if c.id is None:
            continue
        items.append(
            BookCopyRead(
                id=c.id,
                book_id=c.book_id,
                barcode=c.barcode,
                is_checked_out=c.id in busy,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return BookCopyListResponse(items=items)


def create_copy_controller(
    book_id: int,
    payload: BookCopyCreate,
    session: Session,
) -> BookCopyRead:
    book = book_services.get_book_by_id(session, book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book not found",
        )
    try:
        c = copy_services.create_copy_for_book(
            session,
            book_id,
            barcode=payload.barcode,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcode already in use",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    busy = copy_services.copy_ids_with_open_loans(session, [c.id])  # type: ignore[list-item]
    return BookCopyRead(
        id=c.id,  # type: ignore[arg-type]
        book_id=c.book_id,
        barcode=c.barcode,
        is_checked_out=c.id in busy,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def update_copy_controller(
    copy_id: int,
    payload: BookCopyUpdate,
    session: Session,
) -> BookCopyRead:
    c = copy_services.get_copy_by_id(session, copy_id)
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Copy not found",
        )
    data = payload.model_dump(exclude_unset=True)
    try:
        c = copy_services.update_copy(session, c, **data)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Barcode already in use",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    busy = copy_services.copy_has_open_loan(session, c.id)  # type: ignore[arg-type]
    return BookCopyRead(
        id=c.id,  # type: ignore[arg-type]
        book_id=c.book_id,
        barcode=c.barcode,
        is_checked_out=busy,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def delete_copy_controller(copy_id: int, session: Session) -> None:
    c = copy_services.get_copy_by_id(session, copy_id)
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Copy not found",
        )
    try:
        copy_services.soft_delete_copy(session, c)
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
            copy_id=payload.copy_id,
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
    bc = session.get(BookCopy, loan.copy_id)
    if bc is None:
        raise RuntimeError("copy missing after checkout")
    return loan_to_read(session, loan, patron, bc)
