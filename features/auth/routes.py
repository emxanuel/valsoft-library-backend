from fastapi import APIRouter, Cookie, Depends, Response, status
from sqlmodel import Session

from database.session import get_session
from features.auth.controllers import login_controller, register_controller
from features.auth.schemas import LoginRequest, LoginResponse, RegisterRequest, UserRead
from features.auth.dependencies import get_current_user_read
from features.auth.session import invalidate_session


auth_router = APIRouter(tags=["auth"])


@auth_router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegisterRequest,
    session: Session = Depends(get_session),
) -> UserRead:
    return register_controller(payload, session)


@auth_router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
def login(
    payload: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> LoginResponse:
    login_response, session_id = login_controller(payload, session)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return login_response


@auth_router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
)
def read_current_user(
    current_user: UserRead = Depends(get_current_user_read),
) -> UserRead:
    return current_user


@auth_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    response: Response,
    session_id: str | None = Cookie(default=None),
) -> None:
    if session_id is not None:
        invalidate_session(session_id)
        response.delete_cookie(
            key="session_id",
            httponly=True,
            secure=True,
            samesite="lax",
        )
    # Let FastAPI use the configured 204 status with an empty body.
    return None

