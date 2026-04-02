import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, status
from sqlmodel import Session

from database.models.users import Users
from database.session import get_session
from features.auth.dependencies import get_current_user, get_websocket_user
from features.books.ai_services import enrich_book_metadata
from features.books.controllers import (
    checkout_controller,
    create_book_controller,
    create_copy_controller,
    delete_book_controller,
    delete_copy_controller,
    enrich_book_ai_controller,
    get_book_controller,
    list_books_controller,
    list_copies_controller,
    update_book_controller,
    update_copy_controller,
)
from features.books.schemas import (
    BookAiEnrichRequest,
    BookAiEnrichResponse,
    BookCopyCreate,
    BookCopyListResponse,
    BookCopyRead,
    BookCopyUpdate,
    BookCreate,
    BookListPage,
    BookRead,
    BookUpdate,
)
from features.loans.schemas import CheckoutRequest, LoanRead

books_router = APIRouter(tags=["books"])


@books_router.get("/books", response_model=BookListPage)
def list_books(
    q: Optional[str] = Query(default=None, description="Search title, author, or ISBN"),
    genre: Optional[str] = Query(default=None, description="Exact genre match"),
    offset: int = Query(default=0, ge=0, description="Number of rows to skip"),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Page size (max 100)",
    ),
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_user),
) -> BookListPage:
    return list_books_controller(
        session,
        q=q,
        genre=genre,
        offset=offset,
        limit=limit,
    )


@books_router.post(
    "/books",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
)
def create_book(
    payload: BookCreate,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_user),
) -> BookRead:
    return create_book_controller(payload, session)


@books_router.post("/books/ai/enrich", response_model=BookAiEnrichResponse)
def enrich_book_ai(
    payload: BookAiEnrichRequest,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_user),
) -> BookAiEnrichResponse:
    return enrich_book_ai_controller(payload, session)


@books_router.get("/books/{book_id}", response_model=BookRead)
def get_book(
    book_id: int,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_user),
) -> BookRead:
    return get_book_controller(session, book_id)


@books_router.patch("/books/{book_id}", response_model=BookRead)
def update_book(
    book_id: int,
    payload: BookUpdate,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_user),
) -> BookRead:
    return update_book_controller(book_id, payload, session)


@books_router.delete("/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(
    book_id: int,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_user),
) -> None:
    delete_book_controller(book_id, session)
    return None


@books_router.get("/books/{book_id}/copies", response_model=BookCopyListResponse)
def list_book_copies(
    book_id: int,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_user),
) -> BookCopyListResponse:
    return list_copies_controller(session, book_id)


@books_router.post(
    "/books/{book_id}/copies",
    response_model=BookCopyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_book_copy(
    book_id: int,
    payload: BookCopyCreate,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_user),
) -> BookCopyRead:
    return create_copy_controller(book_id, payload, session)


@books_router.patch("/copies/{copy_id}", response_model=BookCopyRead)
def update_book_copy(
    copy_id: int,
    payload: BookCopyUpdate,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_user),
) -> BookCopyRead:
    return update_copy_controller(copy_id, payload, session)


@books_router.delete("/copies/{copy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book_copy(
    copy_id: int,
    session: Session = Depends(get_session),
    _: Users = Depends(get_current_user),
) -> None:
    delete_copy_controller(copy_id, session)
    return None


@books_router.post(
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


@books_router.websocket("/books/ai/enrich/stream")
async def enrich_book_ai_stream(
    websocket: WebSocket,
    session: Session = Depends(get_session),
) -> None:
    await websocket.accept()
    try:
        get_websocket_user(websocket, session)
    except ValueError as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
        await websocket.close(code=1008)
        return

    try:
        raw = await websocket.receive_text()
    except Exception:
        await websocket.send_json({"type": "error", "detail": "Expected a text message"})
        await websocket.close(code=1003)
        return

    try:
        payload = BookAiEnrichRequest.model_validate_json(raw)
    except Exception as exc:
        await websocket.send_json({"type": "error", "detail": f"Invalid payload: {exc}"})
        await websocket.close(code=1003)
        return

    loop = asyncio.get_running_loop()

    def on_progress(step: str, message: str | None) -> None:
        asyncio.run_coroutine_threadsafe(
            websocket.send_json({"type": "progress", "step": step, "message": message}),
            loop,
        ).result()

    def worker() -> BookAiEnrichResponse:
        with Session(session.bind) as thread_session:
            return enrich_book_metadata(thread_session, payload, on_progress=on_progress)

    try:
        result = await asyncio.to_thread(worker)
    except ValueError as exc:
        await websocket.send_json({"type": "error", "detail": str(exc)})
        await websocket.close(code=1011)
        return

    await websocket.send_json({"type": "result", "data": result.model_dump()})
    await websocket.close(code=1000)
