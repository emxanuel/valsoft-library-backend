from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlmodel import Session, col, select

from database.models.books import Book
from database.models.clients import Client
from database.models.loans import Loan


def get_book_by_id(session: Session, book_id: int) -> Optional[Book]:
    book = session.get(Book, book_id)
    if book is None or book.deleted_at is not None:
        return None
    return book


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


def normalize_client_email(email: str) -> str:
    return email.strip().lower()


def get_or_create_client(
    session: Session,
    *,
    name: str,
    email: str,
    phone: Optional[str] = None,
) -> Client:
    norm_email = normalize_client_email(email)
    stmt = select(Client).where(Client.email == norm_email)
    existing = session.exec(stmt).first()
    phone_clean = phone.strip() if phone and phone.strip() else None
    if existing is not None:
        existing.name = name.strip()
        existing.phone = phone_clean
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    client = Client(
        name=name.strip(),
        email=norm_email,
        phone=phone_clean,
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


def _client_search_filters(*, q: Optional[str] = None) -> list:
    filters: list = []
    if q:
        term = f"%{q}%"
        filters.append(
            or_(
                col(Client.name).ilike(term),
                col(Client.email).ilike(term),
            )
        )
    return filters


def list_clients(
    session: Session,
    *,
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Client], int]:
    filters = _client_search_filters(q=q)
    if filters:
        where = and_(*filters)
        count_stmt = select(func.count()).select_from(Client).where(where)
        stmt = (
            select(Client)
            .where(where)
            .order_by(col(Client.name))
            .offset(offset)
            .limit(limit)
        )
    else:
        count_stmt = select(func.count()).select_from(Client)
        stmt = (
            select(Client).order_by(col(Client.name)).offset(offset).limit(limit)
        )
    total = session.exec(count_stmt).one()
    clients = list(session.exec(stmt).all())
    return clients, int(total)


def _active_book_filters(
    *,
    q: Optional[str] = None,
    genre: Optional[str] = None,
) -> list:
    filters: list = [col(Book.deleted_at).is_(None)]
    if q:
        term = f"%{q}%"
        filters.append(
            or_(
                col(Book.title).ilike(term),
                col(Book.author).ilike(term),
                col(Book.isbn).ilike(term),
            )
        )
    if genre:
        filters.append(col(Book.genre) == genre)
    return filters


def list_books(
    session: Session,
    *,
    q: Optional[str] = None,
    genre: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Book], int]:
    filters = _active_book_filters(q=q, genre=genre)
    where = and_(*filters)

    count_stmt = select(func.count()).select_from(Book).where(where)
    total = session.exec(count_stmt).one()

    stmt = (
        select(Book)
        .where(where)
        .order_by(col(Book.title))
        .offset(offset)
        .limit(limit)
    )
    books = list(session.exec(stmt).all())
    return books, int(total)


def create_book(
    session: Session,
    *,
    title: str,
    author: str,
    isbn: Optional[str] = None,
    description: Optional[str] = None,
    published_year: Optional[int] = None,
    genre: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Book:
    book = Book(
        title=title,
        author=author,
        isbn=isbn,
        description=description,
        published_year=published_year,
        genre=genre,
        image_url=image_url,
    )
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


def update_book(
    session: Session,
    book: Book,
    *,
    title: Optional[str] = None,
    author: Optional[str] = None,
    isbn: Optional[str] = None,
    description: Optional[str] = None,
    published_year: Optional[int] = None,
    genre: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Book:
    if title is not None:
        book.title = title
    if author is not None:
        book.author = author
    if isbn is not None:
        book.isbn = isbn
    if description is not None:
        book.description = description
    if published_year is not None:
        book.published_year = published_year
    if genre is not None:
        book.genre = genre
    if image_url is not None:
        book.image_url = image_url
    book.updated_at = datetime.utcnow()
    session.add(book)
    session.commit()
    session.refresh(book)
    return book


def delete_book(session: Session, book: Book) -> None:
    if book_has_open_loan(session, book.id):  # type: ignore[arg-type]
        msg = "Cannot delete a book that is currently checked out"
        raise ValueError(msg)
    book.deleted_at = datetime.utcnow()
    book.updated_at = datetime.utcnow()
    session.add(book)
    session.commit()


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
    if get_book_by_id(session, book_id) is None:
        msg = "Book not found"
        raise ValueError(msg)
    if book_has_open_loan(session, book_id):
        msg = "Book is already checked out"
        raise ValueError(msg)
    client = get_or_create_client(
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
