from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, func, or_
from sqlmodel import Session, col, select

from database.models.clients import Client
from database.models.loans import Loan


def normalize_client_email(email: str) -> str:
    return email.strip().lower()


def get_or_create_client(
    session: Session,
    *,
    name: str,
    email: str,
    phone: Optional[str] = None,
) -> Client:
    norm_email = normalize_client_email(email)
    stmt = select(Client).where(Client.email == norm_email)
    existing = session.exec(stmt).first()
    phone_clean = phone.strip() if phone and phone.strip() else None
    if existing is not None:
        existing.name = name.strip()
        existing.phone = phone_clean
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    client = Client(
        name=name.strip(),
        email=norm_email,
        phone=phone_clean,
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


def _client_search_filters(*, q: Optional[str] = None) -> list:
    filters: list = []
    if q:
        term = f"%{q}%"
        filters.append(
            or_(
                col(Client.name).ilike(term),
                col(Client.email).ilike(term),
            )
        )
    return filters


def count_loans_for_client(session: Session, client_id: int) -> int:
    stmt = select(func.count()).select_from(Loan).where(Loan.client_id == client_id)
    return int(session.exec(stmt).one())


def get_client_by_id(session: Session, client_id: int) -> Optional[Client]:
    return session.get(Client, client_id)


def create_client(
    session: Session,
    *,
    name: str,
    email: str,
    phone: Optional[str] = None,
) -> Client:
    norm_email = normalize_client_email(email)
    stmt = select(Client).where(Client.email == norm_email)
    if session.exec(stmt).first() is not None:
        msg = "A client with this email already exists"
        raise ValueError(msg)
    phone_clean = phone.strip() if phone and phone.strip() else None
    client = Client(
        name=name.strip(),
        email=norm_email,
        phone=phone_clean,
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


def update_client(session: Session, client: Client, patch: dict[str, Any]) -> Client:
    if "name" in patch:
        client.name = patch["name"].strip()
    if "email" in patch:
        norm_email = normalize_client_email(patch["email"])
        if norm_email != client.email:
            stmt = select(Client).where(Client.email == norm_email)
            other = session.exec(stmt).first()
            if other is not None and other.id != client.id:
                msg = "A client with this email already exists"
                raise ValueError(msg)
            client.email = norm_email
    if "phone" in patch:
        p = patch["phone"]
        client.phone = p.strip() if p and str(p).strip() else None
    client.updated_at = datetime.utcnow()
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


def delete_client(session: Session, client: Client) -> None:
    cid = client.id
    if cid is None:
        msg = "Client id missing"
        raise ValueError(msg)
    if count_loans_for_client(session, cid) > 0:
        msg = "Cannot delete a client who has loan history"
        raise ValueError(msg)
    session.delete(client)
    session.commit()


def list_clients(
    session: Session,
    *,
    q: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Client], int]:
    filters = _client_search_filters(q=q)
    if filters:
        where = and_(*filters)
        count_stmt = select(func.count()).select_from(Client).where(where)
        stmt = (
            select(Client)
            .where(where)
            .order_by(col(Client.name))
            .offset(offset)
            .limit(limit)
        )
    else:
        count_stmt = select(func.count()).select_from(Client)
        stmt = (
            select(Client).order_by(col(Client.name)).offset(offset).limit(limit)
        )
    total = session.exec(count_stmt).one()
    clients = list(session.exec(stmt).all())
    return clients, int(total)
