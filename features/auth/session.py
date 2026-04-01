from __future__ import annotations

import secrets
from typing import Dict, Optional


_SESSIONS: Dict[str, int] = {}


def create_session(user_id: int) -> str:
    session_id = secrets.token_urlsafe(32)
    _SESSIONS[session_id] = user_id
    return session_id


def get_user_id_from_session(session_id: str) -> Optional[int]:
    return _SESSIONS.get(session_id)


def invalidate_session(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)

