from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, or_
from sqlmodel import Session, col, select

from database.models.books import Book
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


def list_open_loans_for_user(session: Session, user_id: int) -> list[tuple[Loan, Book]]:
    stmt = (
        select(Loan, Book)
        .join(Book, Loan.book_id == Book.id)  # type: ignore[arg-type]
        .where(Loan.user_id == user_id)
        .where(col(Loan.returned_at).is_(None))
        .where(col(Book.deleted_at).is_(None))
        .order_by(col(Loan.checked_out_at).desc())
    )
    return list(session.exec(stmt).all())


def list_books(
    session: Session,
    *,
    q: Optional[str] = None,
    genre: Optional[str] = None,
) -> list[Book]:
    stmt = select(Book)
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
    if filters:
        stmt = stmt.where(and_(*filters))
    stmt = stmt.order_by(col(Book.title))
    return list(session.exec(stmt).all())


def create_book(
    session: Session,
    *,
    title: str,
    author: str,
    isbn: Optional[str] = None,
    description: Optional[str] = None,
    published_year: Optional[int] = None,
    genre: Optional[str] = None,
) -> Book:
    book = Book(
        title=title,
        author=author,
        isbn=isbn,
        description=description,
        published_year=published_year,
        genre=genre,
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
    due_at: Optional[datetime] = None,
) -> Loan:
    if get_book_by_id(session, book_id) is None:
        msg = "Book not found"
        raise ValueError(msg)
    if book_has_open_loan(session, book_id):
        msg = "Book is already checked out"
        raise ValueError(msg)
    loan = Loan(
        book_id=book_id,
        user_id=user_id,
        due_at=due_at,
        returned_at=None,
    )
    session.add(loan)
    session.commit()
    session.refresh(loan)
    return loan


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
