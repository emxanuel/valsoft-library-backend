# Valsoft Library — Backend API

FastAPI backend for the library app (catalog, circulation, staff auth, optional AI metadata hints).

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL (tests use in-memory SQLite by default)

## Run locally

1. Copy [`.env.example`](.env.example) to `.env` and set **`DATABASE_URL`** (e.g. `postgresql+psycopg://user:pass@localhost:5432/dbname`).

2. Install, migrate, and start:

   ```bash
   uv sync
   uv run alembic upgrade head
   uv run uvicorn main:app --reload
   ```

   Set `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` in `.env` **before** `alembic upgrade` if you need a first admin (see [AGENTS.md](AGENTS.md)). Optional AI enrich: `GEMINI_API_KEY` and `GEMINI_MODEL`.

3. Tests:

   ```bash
   uv run pytest
   ```

Docker: [`Dockerfile`](Dockerfile). Frontend UI: sibling repo **valsoft-library-frontend**. More detail: [ARCHITECTURE.md](ARCHITECTURE.md), [AGENTS.md](AGENTS.md).
