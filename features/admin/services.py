from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from database.models.loans import Loan
from database.models.users import UserRole, Users
from features.auth.services import create_user, get_user_by_email, get_user_by_id, hash_password


def normalize_staff_email(email: str) -> str:
    return email.strip().lower()


def count_admins(session: Session) -> int:
    stmt = select(func.count()).select_from(Users).where(Users.role == UserRole.ADMIN)
    return int(session.exec(stmt).one())


def count_loans_for_user(session: Session, user_id: int) -> int:
    stmt = select(func.count()).select_from(Loan).where(Loan.user_id == user_id)
    return int(session.exec(stmt).one())


def _search_filters(*, q: Optional[str] = None) -> list:
    filters: list = []
    if q:
        term = f"%{q}%"
        filters.append(
            or_(
                col(Users.first_name).ilike(term),
                col(Users.last_name).ilike(term),
                col(Users.email).ilike(term),
            )
        )
    return filters


def list_staff(
    session: Session,
    *,
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Users], int]:
    filters = _search_filters(q=q)
    base = select(Users)
    count_stmt = select(func.count()).select_from(Users)
    if filters:
        for f in filters:
            base = base.where(f)
            count_stmt = count_stmt.where(f)
    total = int(session.exec(count_stmt).one())
    stmt = (
        base.order_by(col(Users.last_name), col(Users.first_name))
        .offset(offset)
        .limit(limit)
    )
    items = list(session.exec(stmt).all())
    return items, total


def create_employee(
    session: Session,
    *,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
) -> Users:
    norm = normalize_staff_email(email)
    if get_user_by_email(session, norm) is not None:
        raise ValueError("Email is already in use")
    return create_user(
        session,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=norm,
        password=password,
        role=UserRole.EMPLOYEE,
    )


def update_staff(
    session: Session,
    *,
    user_id: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[UserRole] = None,
) -> Users:
    user = get_user_by_id(session, user_id)
    if user is None:
        raise ValueError("User not found")

    if first_name is not None:
        user.first_name = first_name.strip()
    if last_name is not None:
        user.last_name = last_name.strip()

    if email is not None:
        norm = normalize_staff_email(str(email))
        other = get_user_by_email(session, norm)
        if other is not None and other.id != user_id:
            raise ValueError("Email is already in use")
        user.email = norm

    if password is not None:
        user.password_hash = hash_password(password)

    if role is not None:
        if user.role == UserRole.ADMIN and role == UserRole.EMPLOYEE:
            if count_admins(session) <= 1:
                raise ValueError("Cannot demote the last admin")
        user.role = role

    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def delete_staff(session: Session, *, user_id: int, acting_user_id: int) -> None:
    if user_id == acting_user_id:
        raise ValueError("Cannot delete your own account")

    user = get_user_by_id(session, user_id)
    if user is None:
        raise ValueError("User not found")

    if count_loans_for_user(session, user_id) > 0:
        raise ValueError("Cannot delete staff with loan history")

    if user.role == UserRole.ADMIN and count_admins(session) <= 1:
        raise ValueError("Cannot delete the last admin")

    session.delete(user)
    session.commit()
