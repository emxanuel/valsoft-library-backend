from __future__ import annotations

import secrets
from typing import Optional

from sqlmodel import Session, select

from database.models.auth_sessions import AuthSession


def create_session(session: Session, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    row = AuthSession(token=token, user_id=user_id)
    session.add(row)
    session.commit()
    return token


def get_user_id_from_session(session: Session, token: str) -> Optional[int]:
    stmt = select(AuthSession).where(AuthSession.token == token)
    row = session.exec(stmt).first()
    return row.user_id if row else None


def invalidate_session(session: Session, token: str) -> None:
    stmt = select(AuthSession).where(AuthSession.token == token)
    row = session.exec(stmt).first()
    if row is None:
        return
    session.delete(row)
    session.commit()
