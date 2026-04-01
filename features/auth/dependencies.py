from __future__ import annotations

from fastapi import Cookie, Depends, HTTPException, status
from sqlmodel import Session

from database.models.users import Users
from database.session import get_session
from features.auth.schemas import UserRead
from features.auth import services
from features.auth.session import get_user_id_from_session


def get_current_user(
    session_id: str | None = Cookie(default=None),
    session: Session = Depends(get_session),
) -> Users:
    if session_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user_id = get_user_id_from_session(session_id)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    user = services.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def get_current_user_read(
    user: Users = Depends(get_current_user),
) -> UserRead:
    return UserRead.model_validate(user, from_attributes=True)

