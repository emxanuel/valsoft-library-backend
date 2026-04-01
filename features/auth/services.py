from collections.abc import Sequence
from typing import Annotated, Optional
import hashlib

from fastapi import Depends
from passlib.context import CryptContext
from sqlmodel import Session, select

from database.session import get_session
from database.models.users import Users


SessionDep = Annotated[Session, Depends(get_session)]

pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _prehash(password: str) -> str:
    """Pre-hash the password to avoid bcrypt's 72-byte limit."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    digest = _prehash(password)
    hashed: str = pwd_context.hash(digest)
    return hashed


def verify_password(plain_password: str, hashed_password: str) -> bool:
    digest = _prehash(plain_password)
    verified: bool = pwd_context.verify(digest, hashed_password)
    return verified


def list_users(session: Session) -> Sequence[Users]:
    statement = select(Users)
    return session.exec(statement).all()


def get_user_by_id(session: Session, user_id: int) -> Optional[Users]:
    statement = select(Users).where(Users.id == user_id)
    return session.exec(statement).first()


def get_user_by_email(session: Session, email: str) -> Optional[Users]:
    statement = select(Users).where(Users.email == email)
    return session.exec(statement).first()


def ensure_email_available(session: Session, email: str) -> None:
    existing = get_user_by_email(session, email)
    if existing is not None:
        msg = "Email is already in use"
        raise ValueError(msg)


def create_user(
    session: Session,
    first_name: str,
    last_name: str,
    email: str,
    password: str,
) -> Users:
    user = Users(
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=hash_password(password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate_user(
    session: Session,
    email: str,
    password: str,
) -> Optional[Users]:
    user = get_user_by_email(session, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


