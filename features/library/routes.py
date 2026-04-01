from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from database.models.users import Users
from database.session import get_session
from features.auth.dependencies import get_current_user
from features.library.controllers import (
    checkin_controller,
    checkout_controller,
    create_book_controller,
    delete_book_controller,
    get_book_controller,
    list_books_controller,
    list_clients_controller,
    list_my_loans_controller,
    update_book_controller,
)
from features.library.schemas import (
    BookCreate,
    BookListPage,
    BookRead,
    BookUpdate,
    CheckoutRequest,
    ClientListPage,
    LoanRead,
    MyOpenLoanRead,
)

library_router = APIRouter(
    tags=["library"],
    dependencies=[Depends(get_current_user)],
)


@library_router.get("/loans", response_model=list[MyOpenLoanRead])
def list_my_loans(
    session: Session = Depends(get_session),
    current_user: Users = Depends(get_current_user),
) -> list[MyOpenLoanRead]:
    return list_my_loans_controller(session, current_user)


@library_router.get("/clients", response_model=ClientListPage)
def list_clients(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(default=None, description="Search name or email"),
    offset: int = Query(default=0, ge=0, description="Number of rows to skip"),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Page size (max 100)",
    ),
) -> ClientListPage:
    return list_clients_controller(session, q=q, offset=offset, limit=limit)


@library_router.get("/books", response_model=BookListPage)
def list_books(
    session: Session = Depends(get_session),
    q: Optional[str] = Query(default=None, description="Search title, author, or ISBN"),
    genre: Optional[str] = Query(default=None, description="Exact genre match"),
    offset: int = Query(default=0, ge=0, description="Number of rows to skip"),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Page size (max 100)",
    ),
) -> BookListPage:
    return list_books_controller(
        session,
        q=q,
        genre=genre,
        offset=offset,
        limit=limit,
    )


@library_router.post(
    "/books",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
)
def create_book(
    payload: BookCreate,
    session: Session = Depends(get_session),
) -> BookRead:
    return create_book_controller(payload, session)


@library_router.get("/books/{book_id}", response_model=BookRead)
def get_book(
    book_id: int,
    session: Session = Depends(get_session),
) -> BookRead:
    return get_book_controller(session, book_id)


@library_router.patch("/books/{book_id}", response_model=BookRead)
def update_book(
    book_id: int,
    payload: BookUpdate,
    session: Session = Depends(get_session),
) -> BookRead:
    return update_book_controller(book_id, payload, session)


@library_router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(
    book_id: int,
    session: Session = Depends(get_session),
) -> None:
    delete_book_controller(book_id, session)
    return None


@library_router.post(
    "/books/{book_id}/checkout",
    response_model=LoanRead,
    status_code=status.HTTP_201_CREATED,
)
def checkout_book(
    book_id: int,
    payload: CheckoutRequest,
    current_user: Users = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LoanRead:
    return checkout_controller(book_id, payload, current_user, session)


@library_router.post("/books/{book_id}/checkin", response_model=LoanRead)
def checkin_book(
    book_id: int,
    current_user: Users = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LoanRead:
    return checkin_controller(book_id, current_user, session)
