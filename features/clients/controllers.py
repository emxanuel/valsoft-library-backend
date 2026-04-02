from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import Session

from features.clients import services as client_services
from features.clients.schemas import (
    ClientCreate,
    ClientListPage,
    ClientRead,
    ClientUpdate,
)


def list_clients_controller(
    session: Session,
    *,
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> ClientListPage:
    clients, total = client_services.list_clients(
        session,
        q=q,
        offset=offset,
        limit=limit,
    )
    items = [ClientRead.model_validate(c, from_attributes=True) for c in clients]
    return ClientListPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_client_controller(session: Session, client_id: int) -> ClientRead:
    client = client_services.get_client_by_id(session, client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    return ClientRead.model_validate(client, from_attributes=True)


def create_client_controller(payload: ClientCreate, session: Session) -> ClientRead:
    try:
        client = client_services.create_client(
            session,
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ClientRead.model_validate(client, from_attributes=True)


def update_client_controller(
    client_id: int,
    payload: ClientUpdate,
    session: Session,
) -> ClientRead:
    client = client_services.get_client_by_id(session, client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    patch = payload.model_dump(exclude_unset=True)
    if not patch:
        return ClientRead.model_validate(client, from_attributes=True)
    try:
        client = client_services.update_client(session, client, patch)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return ClientRead.model_validate(client, from_attributes=True)


def delete_client_controller(client_id: int, session: Session) -> None:
    client = client_services.get_client_by_id(session, client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    try:
        client_services.delete_client(session, client)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
