from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import Session

from database.models.users import UserRole, Users
from features.admin import services as admin_services
from features.auth.services import get_user_by_id
from features.admin.schemas import (
    EmployeeCreate,
    EmployeeUpdate,
    StaffListPage,
    StaffRead,
)


def list_staff_controller(
    session: Session,
    *,
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> StaffListPage:
    rows, total = admin_services.list_staff(
        session, q=q, offset=offset, limit=limit
    )
    items = [StaffRead.model_validate(r, from_attributes=True) for r in rows]
    return StaffListPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_staff_controller(session: Session, user_id: int) -> StaffRead:
    user = get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return StaffRead.model_validate(user, from_attributes=True)


def create_employee_controller(payload: EmployeeCreate, session: Session) -> StaffRead:
    try:
        user = admin_services.create_employee(
            session,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=str(payload.email),
            password=payload.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return StaffRead.model_validate(user, from_attributes=True)


def update_staff_controller(
    payload: EmployeeUpdate,
    session: Session,
    user_id: int,
) -> StaffRead:
    role: Optional[UserRole] = None
    if payload.role is not None:
        role = UserRole(payload.role.value)
    try:
        user = admin_services.update_staff(
            session,
            user_id=user_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=str(payload.email) if payload.email is not None else None,
            password=payload.password,
            role=role,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return StaffRead.model_validate(user, from_attributes=True)


def delete_staff_controller(
    session: Session,
    user_id: int,
    acting_user: Users,
) -> None:
    try:
        admin_services.delete_staff(
            session, user_id=user_id, acting_user_id=acting_user.id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
