from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from database.models.users import Users
from database.session import get_session
from features.auth.dependencies import get_current_user
from features.loans.controllers import (
    checkin_loan_controller,
    list_loan_history_controller,
    list_my_loans_controller,
)
from features.loans.schemas import LoanHistoryPage, LoanRead, MyOpenLoanRead

loans_router = APIRouter(
    tags=["loans"],
    dependencies=[Depends(get_current_user)],
)


@loans_router.get("/loans/history", response_model=LoanHistoryPage)
def list_loan_history(
    session: Session = Depends(get_session),
    current_user: Users = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    client_id: Optional[int] = Query(default=None, ge=1),
) -> LoanHistoryPage:
    return list_loan_history_controller(
        session,
        current_user,
        offset=offset,
        limit=limit,
        client_id=client_id,
    )


@loans_router.get("/loans", response_model=list[MyOpenLoanRead])
def list_my_loans(
    session: Session = Depends(get_session),
    current_user: Users = Depends(get_current_user),
) -> list[MyOpenLoanRead]:
    return list_my_loans_controller(session, current_user)


@loans_router.post("/loans/{loan_id}/checkin", response_model=LoanRead)
def checkin_loan(
    loan_id: int,
    session: Session = Depends(get_session),
    current_user: Users = Depends(get_current_user),
) -> LoanRead:
    return checkin_loan_controller(loan_id, current_user, session)
