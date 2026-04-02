"""Pytest fixtures: set DATABASE_URL before any app imports that build the engine."""

from __future__ import annotations

import os

import pytest

if "TEST_DATABASE_URL" in os.environ:
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
else:
    os.environ["DATABASE_URL"] = "sqlite://"

from core.config import get_settings

get_settings.cache_clear()

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from core.create_app import create_app
from database.models import Book, Client, Loan, Users, UserRole  # noqa: F401
from database.session import get_session
from features.auth.services import create_user

# Register models on metadata for create_all
_ = (Book, Client, Loan, Users)


def _ensure_book_soft_delete_indexes(engine) -> None:
    """Align test DB with production: partial unique ISBN (create_all already has columns)."""
    with engine.begin() as conn:
        if engine.dialect.name != "sqlite":
            conn.execute(
                text("ALTER TABLE book ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP")
            )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_book_deleted_at ON book (deleted_at)"))
        conn.execute(text("DROP INDEX IF EXISTS ix_book_isbn"))
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_book_isbn_active ON book (isbn) "
                "WHERE deleted_at IS NULL AND isbn IS NOT NULL"
            )
        )


def _make_test_engine():
    settings = get_settings()
    url = str(settings.DATABASE_URL)
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(url)


@pytest.fixture(scope="session")
def engine():
    eng = _make_test_engine()
    SQLModel.metadata.create_all(eng)
    _ensure_book_soft_delete_indexes(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine):
    session = Session(engine)
    try:
        yield session
    finally:
        session.rollback()
        if session.bind.dialect.name == "sqlite":
            session.execute(text("DELETE FROM loan"))
            session.execute(text("DELETE FROM client"))
            session.execute(text("DELETE FROM book"))
            session.execute(text("DELETE FROM users"))
        else:
            session.execute(
                text("TRUNCATE loan, client, book, users RESTART IDENTITY CASCADE")
            )
        session.commit()
        session.close()


@pytest.fixture(autouse=True)
def clear_in_memory_sessions():
    yield
    from features.auth import session as auth_session

    auth_session._SESSIONS.clear()


@pytest.fixture(autouse=True)
def reset_settings_cache():
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(db_session: Session):
    app = create_app()

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_user(
    client: TestClient,
    *,
    email: str = "alice@example.com",
    password: str = "password123",
    first_name: str = "Alice",
    last_name: str = "Example",
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": password,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login_user(client: TestClient, email: str, password: str) -> dict:
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_staff_in_db(
    session: Session,
    *,
    email: str = "admin@example.com",
    password: str = "password123",
    first_name: str = "Admin",
    last_name: str = "User",
    role: UserRole = UserRole.EMPLOYEE,
) -> Users:
    """Create a user row directly via the same service as the app (hashed password)."""
    return create_user(
        session,
        first_name,
        last_name,
        email,
        password,
        role=role,
    )


@pytest.fixture
def admin_client(client: TestClient, db_session: Session):
    create_staff_in_db(
        db_session,
        email="admin@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    login_user(client, "admin@example.com", "password123")
    return client


@pytest.fixture
def authenticated_client(client: TestClient):
    email = "user@example.com"
    password = "password123"
    register_user(client, email=email, password=password)
    login_user(client, email=email, password=password)
    return client


@pytest.fixture
def authenticated_client_factory(db_session: Session):
    """New app + client per call, shared DB session (same data, isolated cookies)."""

    def _make(*, email: str, password: str = "password123") -> TestClient:
        app = create_app()

        def override_get_session():
            yield db_session

        app.dependency_overrides[get_session] = override_get_session
        test_client = TestClient(app, base_url="https://testserver")
        register_user(test_client, email=email, password=password)
        login_user(test_client, email, password)
        return test_client

    return _make
