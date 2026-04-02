from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from database.models.users import Users
from database.session import get_session
from features.admin.controllers import (
    create_employee_controller,
    delete_staff_controller,
    get_staff_controller,
    list_staff_controller,
    update_staff_controller,
)
from features.admin.schemas import EmployeeCreate, EmployeeUpdate, StaffListPage, StaffRead
from features.auth.dependencies import get_current_admin

admin_router = APIRouter(tags=["admin"])


@admin_router.get("/employees", response_model=StaffListPage)
def list_staff(
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_admin),
    q: Optional[str] = Query(default=None, description="Search name or email"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> StaffListPage:
    return list_staff_controller(session, q=q, offset=offset, limit=limit)


@admin_router.post(
    "/employees",
    response_model=StaffRead,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    payload: EmployeeCreate,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_admin),
) -> StaffRead:
    return create_employee_controller(payload, session)


@admin_router.get("/employees/{user_id}", response_model=StaffRead)
def get_staff(
    user_id: int,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_admin),
) -> StaffRead:
    return get_staff_controller(session, user_id)


@admin_router.patch("/employees/{user_id}", response_model=StaffRead)
def update_staff(
    user_id: int,
    payload: EmployeeUpdate,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_admin),
) -> StaffRead:
    return update_staff_controller(payload, session, user_id)


@admin_router.delete("/employees/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_staff(
    user_id: int,
    session: Session = Depends(get_session),
    acting_user: Users = Depends(get_current_admin),
) -> None:
    delete_staff_controller(session, user_id, acting_user)
