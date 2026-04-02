"""add book_copy table; loan.copy_id replaces loan.book_id

Revision ID: i1a2b3c4d5e6
Revises: h0a1b2c3d4e5
Create Date: 2026-04-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i1a2b3c4d5e6"
down_revision: Union[str, None] = "h0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fk_on_column(table: str, column: str) -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    for fk in insp.get_foreign_keys(table):
        if column in fk["constrained_columns"]:
            op.drop_constraint(fk["name"], table, type_="foreignkey")
            return
    raise RuntimeError(f"No FK on {table}.{column} found")


def upgrade() -> None:
    op.create_table(
        "book_copy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("barcode", sa.String(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["book_id"], ["book.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_book_copy_book_id"), "book_copy", ["book_id"], unique=False)
    op.create_index(op.f("ix_book_copy_barcode"), "book_copy", ["barcode"], unique=False)
    op.create_index(op.f("ix_book_copy_deleted_at"), "book_copy", ["deleted_at"], unique=False)

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO book_copy (book_id, barcode, deleted_at, created_at, updated_at)
            SELECT id, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM book ORDER BY id
            """
        )
    )

    op.add_column(
        "loan",
        sa.Column("copy_id", sa.Integer(), nullable=True),
    )
    op.create_index(op.f("ix_loan_copy_id"), "loan", ["copy_id"], unique=False)

    conn.execute(
        sa.text(
            """
            UPDATE loan
            SET copy_id = (
                SELECT bc.id FROM book_copy bc
                WHERE bc.book_id = loan.book_id
                ORDER BY bc.id
                LIMIT 1
            )
            """
        )
    )

    op.alter_column("loan", "copy_id", existing_type=sa.Integer(), nullable=False)

    op.create_foreign_key(
        "fk_loan_copy_id_book_copy",
        "loan",
        "book_copy",
        ["copy_id"],
        ["id"],
    )

    _drop_fk_on_column("loan", "book_id")
    op.drop_column("loan", "book_id")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uq_book_copy_barcode_active",
            "book_copy",
            ["barcode"],
            unique=True,
            postgresql_where=sa.text("deleted_at IS NULL AND barcode IS NOT NULL"),
        )
    else:
        op.create_index(
            "uq_book_copy_barcode_active",
            "book_copy",
            ["barcode"],
            unique=True,
            sqlite_where=sa.text("deleted_at IS NULL AND barcode IS NOT NULL"),
        )


def downgrade() -> None:
    op.drop_index("uq_book_copy_barcode_active", table_name="book_copy")

    op.add_column(
        "loan",
        sa.Column("book_id", sa.Integer(), nullable=True),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE loan
            SET book_id = (
                SELECT bc.book_id FROM book_copy bc WHERE bc.id = loan.copy_id
            )
            """
        )
    )
    op.alter_column("loan", "book_id", existing_type=sa.Integer(), nullable=False)

    _drop_fk_on_column("loan", "copy_id")
    op.drop_index(op.f("ix_loan_copy_id"), table_name="loan")
    op.drop_column("loan", "copy_id")

    op.create_foreign_key(
        "loan_book_id_fkey",
        "loan",
        "book",
        ["book_id"],
        ["id"],
    )

    op.drop_table("book_copy")
