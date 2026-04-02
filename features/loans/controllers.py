from __future__ import annotations

from sqlmodel import Session

from database.models.clients import Client
from database.models.users import Users
from features.loans import services as loan_services
from features.loans.schemas import MyOpenLoanRead


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


def list_my_loans_controller(
    session: Session,
    current_user: Users,
) -> list[MyOpenLoanRead]:
    rows = loan_services.list_open_loans_for_user(
        session,
        current_user.id,  # type: ignore[arg-type]
    )
    result: list[MyOpenLoanRead] = []
    for loan, book, patron in rows:
        lid = loan.id
        bid = book.id
        if lid is None or bid is None:
            raise RuntimeError("loan or book id missing after persist")
        cid, cname, cemail, cphone = _loan_client_fields(patron)
        result.append(
            MyOpenLoanRead(
                loan_id=lid,
                book_id=bid,
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
