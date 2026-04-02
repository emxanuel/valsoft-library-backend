from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlmodel import Session, col, select

from database.models.books import Book
from features.loans import services as loan_services


def get_book_by_id(session: Session, book_id: int) -> Optional[Book]:
    book = session.get(Book, book_id)
    if book is None or book.deleted_at is not None:
        return None
    return book


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
    if loan_services.book_has_open_loan(session, book.id):  # type: ignore[arg-type]
        msg = "Cannot delete a book that is currently checked out"
        raise ValueError(msg)
    book.deleted_at = datetime.utcnow()
    book.updated_at = datetime.utcnow()
    session.add(book)
    session.commit()
