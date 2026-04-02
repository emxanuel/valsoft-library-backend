"""seed first admin user from SEED_ADMIN_* env

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-04-02

"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g8b9c0d1e2f3"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def upgrade() -> None:
    email = os.environ.get("SEED_ADMIN_EMAIL")
    password = os.environ.get("SEED_ADMIN_PASSWORD")
    if not email or not password:
        raise RuntimeError(
            "Seed admin migration requires SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD "
            "to be set in the environment when running `alembic upgrade`."
        )

    from features.auth.services import hash_password

    email_norm = _normalize_email(email)
    first_name = os.environ.get("SEED_ADMIN_FIRST_NAME", "Admin").strip() or "Admin"
    last_name = os.environ.get("SEED_ADMIN_LAST_NAME", "User").strip() or "User"
    pwd_hash = hash_password(password)
    now = datetime.utcnow()

    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM users WHERE email = :e"),
        {"e": email_norm},
    ).scalar()
    if existing is not None:
        return

    conn.execute(
        sa.text(
            """
            INSERT INTO users (
                first_name, last_name, email, password_hash, role, created_at, updated_at
            )
            VALUES (:fn, :ln, :em, :ph, 'admin', :ca, :ua)
            """
        ),
        {
            "fn": first_name,
            "ln": last_name,
            "em": email_norm,
            "ph": pwd_hash,
            "ca": now,
            "ua": now,
        },
    )


def downgrade() -> None:
    email = os.environ.get("SEED_ADMIN_EMAIL")
    if not email:
        raise RuntimeError(
            "Downgrade requires SEED_ADMIN_EMAIL in the environment (same as used for upgrade)."
        )
    email_norm = _normalize_email(email)
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM users WHERE email = :e"), {"e": email_norm})
