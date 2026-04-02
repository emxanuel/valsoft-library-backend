from fastapi import APIRouter, Depends
from sqlmodel import Session

from database.models.users import Users
from database.session import get_session
from features.auth.dependencies import get_current_user
from features.loans.controllers import list_my_loans_controller
from features.loans.schemas import MyOpenLoanRead

loans_router = APIRouter(
    tags=["loans"],
    dependencies=[Depends(get_current_user)],
)


@loans_router.get("/loans", response_model=list[MyOpenLoanRead])
def list_my_loans(
    session: Session = Depends(get_session),
    current_user: Users = Depends(get_current_user),
) -> list[MyOpenLoanRead]:
    return list_my_loans_controller(session, current_user)
