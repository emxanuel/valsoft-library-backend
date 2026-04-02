from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from database.session import get_session
from features.auth.dependencies import get_current_user
from features.clients.controllers import (
    create_client_controller,
    delete_client_controller,
    get_client_controller,
    list_clients_controller,
    update_client_controller,
)
from features.clients.schemas import ClientCreate, ClientListPage, ClientRead, ClientUpdate

clients_router = APIRouter(
    tags=["clients"],
    dependencies=[Depends(get_current_user)],
)


@clients_router.get("/clients", response_model=ClientListPage)
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


@clients_router.post(
    "/clients",
    response_model=ClientRead,
    status_code=status.HTTP_201_CREATED,
)
def create_client(
    payload: ClientCreate,
    session: Session = Depends(get_session),
) -> ClientRead:
    return create_client_controller(payload, session)


@clients_router.get("/clients/{client_id}", response_model=ClientRead)
def get_client(
    client_id: int,
    session: Session = Depends(get_session),
) -> ClientRead:
    return get_client_controller(session, client_id)


@clients_router.patch("/clients/{client_id}", response_model=ClientRead)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    session: Session = Depends(get_session),
) -> ClientRead:
    return update_client_controller(client_id, payload, session)


@clients_router.delete("/clients/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    session: Session = Depends(get_session),
) -> None:
    delete_client_controller(client_id, session)
    return None
