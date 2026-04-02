"""fix users.role: VARCHAR storing admin/employee values (not PG native enum)

SQLAlchemy mapped UserRole to a PostgreSQL ENUM with labels ADMIN/EMPLOYEE while
migrations and seeds use lowercase 'admin'/'employee'. This revision converts
any existing native enum column to VARCHAR(20) when needed.

Revision ID: h0a1b2c3d4e5
Revises: g8b9c0d1e2f3
Create Date: 2026-04-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h0a1b2c3d4e5"
down_revision: Union[str, None] = "g8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    row = conn.execute(
        sa.text(
            """
            SELECT c.data_type, c.udt_name
            FROM information_schema.columns c
            WHERE c.table_schema = 'public'
              AND c.table_name = 'users'
              AND c.column_name = 'role'
            """
        )
    ).fetchone()
    if not row:
        return

    _data_type, udt_name = row
    if udt_name in ("varchar", "text", "character varying"):
        return

    op.execute(sa.text("ALTER TABLE users ALTER COLUMN role DROP DEFAULT"))
    op.execute(
        sa.text(
            """
            ALTER TABLE users
            ALTER COLUMN role TYPE VARCHAR(20)
            USING (
                CASE role::text
                    WHEN 'ADMIN' THEN 'admin'
                    WHEN 'EMPLOYEE' THEN 'employee'
                    WHEN 'admin' THEN 'admin'
                    WHEN 'employee' THEN 'employee'
                    ELSE lower(role::text)
                END
            )
            """
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE users ALTER COLUMN role SET DEFAULT 'employee'"
        )
    )
    op.execute(sa.text("DROP TYPE IF EXISTS userrole CASCADE"))


def downgrade() -> None:
    pass
