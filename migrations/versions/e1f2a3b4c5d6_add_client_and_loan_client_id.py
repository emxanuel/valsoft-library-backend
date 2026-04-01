"""add client table and loan.client_id

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-04-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_client_email"), "client", ["email"], unique=True)
    op.create_index(op.f("ix_client_name"), "client", ["name"], unique=False)
    op.add_column(
        "loan",
        sa.Column("client_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_loan_client_id_client",
        "loan",
        "client",
        ["client_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_loan_client_id_client", "loan", type_="foreignkey")
    op.drop_column("loan", "client_id")
    op.drop_index(op.f("ix_client_name"), table_name="client")
    op.drop_index(op.f("ix_client_email"), table_name="client")
    op.drop_table("client")
