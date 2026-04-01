"""add book image_url

Revision ID: d4e5f6a7b8c9
Revises: c2f8a1b9e4d0
Create Date: 2026-04-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c2f8a1b9e4d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "book",
        sa.Column("image_url", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("book", "image_url")
