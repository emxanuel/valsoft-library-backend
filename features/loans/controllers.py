from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session

from database.models.book_copies import BookCopy
from database.models.books import Book
from database.models.clients import Client
from database.models.loans import Loan
from database.models.users import Users
from features.loans import services as loan_services
from features.loans.schemas import LoanRead, MyOpenLoanRead


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
