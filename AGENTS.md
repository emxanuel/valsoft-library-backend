# Agent / contributor guide

This document helps humans and coding agents work on the **valsoft-library-backend** project. Update it when you add features, change conventions, or alter how the app is run.

## Stack

- **Python** 3.11+
- **FastAPI** for HTTP APIs
- **SQLModel** (SQLAlchemy + Pydantic) for database models
- **PostgreSQL** (via `psycopg`)
- **Alembic** for migrations
- **uv** for dependency management (`uv sync`, `uv run`)

## Project layout

| Area | Role |
|------|------|
| [`core/`](core/) | App factory ([`create_app.py`](core/create_app.py)), config, logging |
| [`database/models/`](database/models/) | SQLModel table definitions |
| [`database/session.py`](database/session.py) | Engine and `get_session` dependency |
| [`features/<name>/`](features/) | Vertical slices: `routes` → `controllers` → `services`, plus `schemas` |
| [`middlewares/`](middlewares/) | Cross-cutting HTTP concerns (e.g. exception handling) |
| [`migrations/`](migrations/) | Alembic revisions |

### Feature module pattern (see [`features/auth/`](features/auth/), [`features/books/`](features/books/), [`features/loans/`](features/loans/), [`features/clients/`](features/clients/))

- **`schemas.py`** — Pydantic request/response models (API contract). No DB calls.
- **`services.py`** — Database and domain logic. Raises `ValueError` for business-rule failures; returns models or primitives.
- **`controllers.py`** — Maps service outcomes to HTTP: translates `ValueError` and missing entities into `HTTPException`, builds response DTOs.
- **`routes.py`** — FastAPI `APIRouter`: dependencies (`Depends(get_session)`, `Depends(get_current_user)`), HTTP method/path, delegates to controllers.

Routers are registered in [`core/create_app.py`](core/create_app.py) with a URL prefix (e.g. `/auth`, `/library`). The books, loans, and clients routers are each included with `prefix="/library"` so the public paths stay `/library/books`, `/library/loans`, `/library/clients`.

## Authentication

Session cookies (`session_id`) identify the user. Use `Depends(get_current_user)` from [`features/auth/dependencies.py`](features/auth/dependencies.py) when an endpoint requires a logged-in user.

## Library API (`/library`)

Implemented across [`features/books/`](features/books/) (catalog and checkout/check-in), [`features/loans/`](features/loans/) (open loans list), and [`features/clients/`](features/clients/) (patron directory).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/library/books` | Paginated list; optional `q`, `genre`; `offset` (default 0), `limit` (default 20, max 100). JSON: `items`, `total`, `limit`, `offset` |
| `POST` | `/library/books` | Create a book |
| `GET` | `/library/books/{book_id}` | Get one book (`is_checked_out` reflects active loan) |
| `PATCH` | `/library/books/{book_id}` | Update a book |
| `DELETE` | `/library/books/{book_id}` | Soft delete: sets `deleted_at` (row kept); fails if the book is checked out. Loan history is not removed. |
| `GET` | `/library/loans` | Open loans for the current user; includes book fields and patron (`client_*`) when `loan.client_id` is set |
| `GET` | `/library/clients` | Paginated patron directory; optional `q` (name/email); `offset`, `limit` (default 20, max 100). JSON: `items`, `total`, `limit`, `offset` |
| `POST` | `/library/clients` | Create a patron (`name`, `email`, optional `phone`). Email is normalized (trim, lower); **create-only** — duplicate email returns 400 (checkout still upserts via `get_or_create_client`). |
| `GET` | `/library/clients/{client_id}` | Get one patron |
| `PATCH` | `/library/clients/{client_id}` | Update patron fields; email uniqueness enforced among clients |
| `DELETE` | `/library/clients/{client_id}` | Remove patron row; **400** if any `loan` references this `client_id` (open or returned) |
| `POST` | `/library/books/{book_id}/checkout` | Staff checkout; body: `client` (`name`, `email`, optional `phone`) and optional `due_at`. Upserts `client` by normalized email and sets `loan.client_id`. |
| `POST` | `/library/books/{book_id}/checkin` | Return the book (same staff user who checked out; see below) |

Circulation is stored in the `loan` table; **checked out** means an open loan (`returned_at` is null). **Checked in** sets `returned_at`. Patron contact info lives in the `client` table; each new checkout links the loan via `client_id` (nullable for legacy rows). The loan’s `user_id` is the staff account that performed checkout/check-in.

List and get endpoints only return books with `deleted_at` null. ISBN uniqueness applies to active (non-deleted) rows only, so a new book can reuse an ISBN after the previous copy was soft-deleted.

## Database

- Configure `DATABASE_URL` in `.env` (see `.env.example`).
- After model changes: `uv run alembic revision --autogenerate -m "description"` then review the migration, then `uv run alembic upgrade head`.

## Running locally

```bash
uv sync
uv run uvicorn main:app --reload
```

Adjust the app import if your ASGI entrypoint differs from `main:app`.

## Tests

```bash
uv run pytest
```

By default, [`tests/conftest.py`](tests/conftest.py) uses an **in-memory SQLite** database (`DATABASE_URL=sqlite://`) with a `StaticPool` so no local PostgreSQL is required. Set **`TEST_DATABASE_URL`** to a `postgresql+psycopg://` URL to run tests against Postgres instead (e.g. for parity with production).

Add tests under `tests/` following existing patterns in [`tests/conftest.py`](tests/conftest.py) if present.

## Error handling

[`middlewares/exception_handler.py`](middlewares/exception_handler.py) maps validation errors, HTTP exceptions, and database errors to JSON responses. Prefer raising `HTTPException` in controllers for expected API errors.
