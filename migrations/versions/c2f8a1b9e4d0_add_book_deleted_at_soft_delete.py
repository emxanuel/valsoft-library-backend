"""add book deleted_at and partial unique index on isbn

Revision ID: c2f8a1b9e4d0
Revises: b600c6d713c3
Create Date: 2026-04-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2f8a1b9e4d0"
down_revision: Union[str, None] = "b600c6d713c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "book",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_book_deleted_at"), "book", ["deleted_at"], unique=False)
    op.drop_index(op.f("ix_book_isbn"), table_name="book")
    op.create_index(
        "uq_book_isbn_active",
        "book",
        ["isbn"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND isbn IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_book_isbn_active", table_name="book")
    op.create_index(
        op.f("ix_book_isbn"),
        "book",
        ["isbn"],
        unique=True,
    )
    op.drop_index(op.f("ix_book_deleted_at"), table_name="book")
    op.drop_column("book", "deleted_at")
