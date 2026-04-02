from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, col, select

from database.models.book_copies import BookCopy
from database.models.books import Book
from database.models.loans import Loan


def get_copy_by_id(session: Session, copy_id: int) -> Optional[BookCopy]:
    row = session.get(BookCopy, copy_id)
    if row is None or row.deleted_at is not None:
        return None
    return row


def get_copy_by_id_including_deleted(session: Session, copy_id: int) -> Optional[BookCopy]:
    return session.get(BookCopy, copy_id)


def list_copies_for_book(session: Session, book_id: int) -> list[BookCopy]:
    stmt = (
        select(BookCopy)
        .where(BookCopy.book_id == book_id)
        .where(col(BookCopy.deleted_at).is_(None))
        .order_by(col(BookCopy.id))
    )
    return list(session.exec(stmt).all())


def count_total_copies(session: Session, book_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(BookCopy)
        .where(BookCopy.book_id == book_id)
        .where(col(BookCopy.deleted_at).is_(None))
    )
    return int(session.exec(stmt).one())


def copy_stats_for_book_ids(session: Session, book_ids: list[int]) -> dict[int, tuple[int, int]]:
    """Return ``book_id -> (total_copies, available_copies)`` in two queries.

    Used by book list to avoid per-row copy counts (N+1 queries).
    """
    if not book_ids:
        return {}
    stmt = (
        select(BookCopy.id, BookCopy.book_id)
        .where(col(BookCopy.book_id).in_(book_ids))
        .where(col(BookCopy.deleted_at).is_(None))
    )
    rows = session.exec(stmt).all()
    by_book: dict[int, list[int]] = {}
    all_copy_ids: list[int] = []
    for cid, bid in rows:
        if cid is None:
            continue
        all_copy_ids.append(cid)
        by_book.setdefault(bid, []).append(cid)
    busy = copy_ids_with_open_loans(session, all_copy_ids)
    out: dict[int, tuple[int, int]] = {}
    for bid in book_ids:
        ids = by_book.get(bid, [])
        total = len(ids)
        available = sum(1 for i in ids if i not in busy)
        out[bid] = (total, available)
    return out


def copy_ids_with_open_loans(session: Session, copy_ids: list[int]) -> set[int]:
    if not copy_ids:
        return set()
    stmt = (
        select(Loan.copy_id)
        .where(col(Loan.copy_id).in_(copy_ids))
        .where(col(Loan.returned_at).is_(None))
    )
    return set(session.exec(stmt).all())


def copy_has_open_loan(session: Session, copy_id: int) -> bool:
    stmt = (
        select(Loan.id)
        .where(Loan.copy_id == copy_id)
        .where(col(Loan.returned_at).is_(None))
        .limit(1)
    )
    return session.exec(stmt).first() is not None


def find_first_available_copy_id(session: Session, book_id: int) -> Optional[int]:
    """Lowest id among active copies with no open loan."""
    copies = list_copies_for_book(session, book_id)
    if not copies:
        return None
    ids = [c.id for c in copies if c.id is not None]
    if not ids:
        return None
    busy = copy_ids_with_open_loans(session, ids)
    for cid in sorted(ids):
        if cid not in busy:
            return cid
    return None


def create_copy_for_book(
    session: Session,
    book_id: int,
    *,
    barcode: Optional[str] = None,
) -> BookCopy:
    bc = BookCopy(
        book_id=book_id,
        barcode=barcode.strip() if barcode else None,
    )
    session.add(bc)
    session.commit()
    session.refresh(bc)
    return bc


def update_copy(
    session: Session,
    copy: BookCopy,
    *,
    barcode: Optional[str] = None,
) -> BookCopy:
    if barcode is not None:
        copy.barcode = barcode.strip() if barcode.strip() else None
    copy.updated_at = datetime.utcnow()
    session.add(copy)
    session.commit()
    session.refresh(copy)
    return copy


def soft_delete_copy(session: Session, copy: BookCopy) -> None:
    if copy_has_open_loan(session, copy.id):  # type: ignore[arg-type]
        msg = "Cannot delete a copy that is currently checked out"
        raise ValueError(msg)
    copy.deleted_at = datetime.utcnow()
    copy.updated_at = datetime.utcnow()
    session.add(copy)
    session.commit()


def soft_delete_all_copies_for_book(session: Session, book_id: int) -> None:
    for c in list_copies_for_book(session, book_id):
        if copy_has_open_loan(session, c.id):  # type: ignore[arg-type]
            msg = "Cannot delete a book while a copy is checked out"
            raise ValueError(msg)
        c.deleted_at = datetime.utcnow()
        c.updated_at = datetime.utcnow()
        session.add(c)
    session.commit()


def any_copy_has_open_loan(session: Session, book_id: int) -> bool:
    stmt = (
        select(Loan.id)
        .join(BookCopy, Loan.copy_id == BookCopy.id)  # type: ignore[arg-type]
        .where(BookCopy.book_id == book_id)
        .where(col(BookCopy.deleted_at).is_(None))
        .where(col(Loan.returned_at).is_(None))
        .limit(1)
    )
    return session.exec(stmt).first() is not None


def book_has_no_copies_available(session: Session, book_id: int) -> bool:
    """True when there are no lendable copies (no active copies, or all on loan)."""
    return find_first_available_copy_id(session, book_id) is None


def available_copies_count(session: Session, book_id: int) -> int:
    copies = list_copies_for_book(session, book_id)
    ids = [c.id for c in copies if c.id is not None]
    if not ids:
        return 0
    busy = copy_ids_with_open_loans(session, ids)
    return sum(1 for i in ids if i not in busy)
