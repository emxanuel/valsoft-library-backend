from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import Session

from database.models.book_copies import BookCopy
from database.models.books import Book
from database.models.clients import Client
from database.models.loans import Loan
from database.models.users import Users
from features.clients import services as client_services
from features.loans import services as loan_services
from features.loans.schemas import (
    AdminOpenLoanRead,
    AdminOpenLoansPage,
    LoanHistoryPage,
    LoanHistoryRead,
    LoanRead,
    MyOpenLoanRead,
)


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


def loan_to_read(
    session: Session,
    loan: Loan,
    patron: Client | None,
    book_copy: BookCopy,
) -> LoanRead:
    book = session.get(Book, book_copy.book_id)
    if book is None or book.id is None:
        raise RuntimeError("book missing for copy")
    lid = loan.id
    bid = book.id
    cid_copy = loan.copy_id
    uid = loan.user_id
    if lid is None or cid_copy is None or uid is None:
        raise RuntimeError("loan ids missing after persist")
    cid, cname, cemail, cphone = _loan_client_fields(patron)
    return LoanRead(
        id=lid,
        book_id=bid,
        copy_id=cid_copy,
        copy_barcode=book_copy.barcode,
        user_id=uid,
        client_id=cid,
        client_name=cname,
        client_email=cemail,
        client_phone=cphone,
        checked_out_at=loan.checked_out_at,
        due_at=loan.due_at,
        returned_at=loan.returned_at,
    )


def list_my_loans_controller(
    session: Session,
    current_user: Users,
) -> list[MyOpenLoanRead]:
    rows = loan_services.list_open_loans_for_user(
        session,
        current_user.id,  # type: ignore[arg-type]
    )
    result: list[MyOpenLoanRead] = []
    for loan, book_copy, book, patron in rows:
        lid = loan.id
        bid = book.id
        if lid is None or bid is None:
            raise RuntimeError("loan or book id missing after persist")
        cid_copy = book_copy.id
        if cid_copy is None:
            raise RuntimeError("copy id missing")
        cid, cname, cemail, cphone = _loan_client_fields(patron)
        result.append(
            MyOpenLoanRead(
                loan_id=lid,
                book_id=bid,
                copy_id=cid_copy,
                copy_barcode=book_copy.barcode,
                book_title=book.title,
                book_author=book.author,
                client_id=cid,
                client_name=cname,
                client_email=cemail,
                client_phone=cphone,
                checked_out_at=loan.checked_out_at,
                due_at=loan.due_at,
            )
        )
    return result


def list_admin_open_loans_controller(
    session: Session,
    *,
    offset: int,
    limit: int,
) -> AdminOpenLoansPage:
    rows, total = loan_services.list_all_open_loans_paginated(
        session,
        offset=offset,
        limit=limit,
    )
    items: list[AdminOpenLoanRead] = []
    for loan, book_copy, book, patron, staff in rows:
        lid = loan.id
        bid = book.id
        sid = staff.id
        if lid is None or bid is None or sid is None:
            raise RuntimeError("loan, book, or staff id missing after persist")
        cid_copy = book_copy.id
        if cid_copy is None:
            raise RuntimeError("copy id missing")
        cid, cname, cemail, cphone = _loan_client_fields(patron)
        items.append(
            AdminOpenLoanRead(
                loan_id=lid,
                book_id=bid,
                copy_id=cid_copy,
                copy_barcode=book_copy.barcode,
                book_title=book.title,
                book_author=book.author,
                client_id=cid,
                client_name=cname,
                client_email=cemail,
                client_phone=cphone,
                checked_out_at=loan.checked_out_at,
                due_at=loan.due_at,
                staff_user_id=sid,
                staff_email=staff.email,
                staff_first_name=staff.first_name,
                staff_last_name=staff.last_name,
            )
        )
    return AdminOpenLoansPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def _loan_history_read(
    loan: Loan,
    book_copy: BookCopy,
    book: Book,
    patron: Client | None,
    *,
    staff_email: Optional[str] = None,
) -> LoanHistoryRead:
    lid = loan.id
    bid = book.id
    if lid is None or bid is None:
        raise RuntimeError("loan or book id missing after persist")
    cid_copy = book_copy.id
    if cid_copy is None:
        raise RuntimeError("copy id missing")
    cid, cname, cemail, cphone = _loan_client_fields(patron)
    return LoanHistoryRead(
        loan_id=lid,
        book_id=bid,
        copy_id=cid_copy,
        copy_barcode=book_copy.barcode,
        book_title=book.title,
        book_author=book.author,
        client_id=cid,
        client_name=cname,
        client_email=cemail,
        client_phone=cphone,
        checked_out_at=loan.checked_out_at,
        due_at=loan.due_at,
        returned_at=loan.returned_at,
        staff_email=staff_email,
    )


def list_loan_history_controller(
    session: Session,
    current_user: Users,
    *,
    offset: int,
    limit: int,
    client_id: Optional[int] = None,
) -> LoanHistoryPage:
    if client_id is not None:
        if client_services.get_client_by_id(session, client_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found",
            )
        client_rows, total = loan_services.list_client_loan_history_paginated(
            session,
            client_id=client_id,
            offset=offset,
            limit=limit,
        )
        items: list[LoanHistoryRead] = []
        for loan, book_copy, book, patron, staff in client_rows:
            email = staff.email if staff is not None else None
            items.append(
                _loan_history_read(
                    loan,
                    book_copy,
                    book,
                    patron,
                    staff_email=email,
                )
            )
        return LoanHistoryPage(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    staff_rows, total = loan_services.list_staff_loan_history_paginated(
        session,
        user_id=current_user.id,  # type: ignore[arg-type]
        offset=offset,
        limit=limit,
    )
    staff_items = [
        _loan_history_read(loan, book_copy, book, patron, staff_email=None)
        for loan, book_copy, book, patron in staff_rows
    ]
    return LoanHistoryPage(
        items=staff_items,
        total=total,
        limit=limit,
        offset=offset,
    )


def checkin_loan_controller(
    loan_id: int,
    current_user: Users,
    session: Session,
) -> LoanRead:
    try:
        loan = loan_services.checkin_loan(
            session,
            loan_id=loan_id,
            acting_user_id=current_user.id,  # type: ignore[arg-type]
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "No active loan for this id":
            st = status.HTTP_404_NOT_FOUND
        elif detail == "Only the borrower can check in this loan":
            st = status.HTTP_403_FORBIDDEN
        else:
            st = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=st, detail=detail) from exc
    bc = session.get(BookCopy, loan.copy_id)
    if bc is None:
        raise RuntimeError("copy missing after checkin")
    patron = session.get(Client, loan.client_id) if loan.client_id else None
    return loan_to_read(session, loan, patron, bc)
