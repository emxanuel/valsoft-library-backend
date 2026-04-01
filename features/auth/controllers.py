from typing import Tuple

from fastapi import HTTPException, status
from sqlmodel import Session

from features.auth.schemas import LoginRequest, LoginResponse, RegisterRequest, UserRead
from features.auth.services import (
    authenticate_user,
    create_user,
    ensure_email_available,
)
from features.auth.session import create_session


def register_controller(payload: RegisterRequest, session: Session) -> UserRead:
    try:
        ensure_email_available(session, payload.email)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    user = create_user(
        session=session,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        password=payload.password,
    )
    return UserRead.model_validate(user, from_attributes=True)


def login_controller(payload: LoginRequest, session: Session) -> Tuple[LoginResponse, str]:
    user = authenticate_user(session, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    session_id = create_session(user.id)  # type: ignore[arg-type]
    user_read = UserRead.model_validate(user, from_attributes=True)
    login_response = LoginResponse(user=user_read)
    return login_response, session_id

