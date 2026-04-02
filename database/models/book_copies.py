from datetime import datetime
from typing import Optional

from sqlalchemy import Index, text
from sqlmodel import Field, SQLModel


class BookCopy(SQLModel, table=True):
    __tablename__ = "book_copy"

    __table_args__ = (
        Index(
            "uq_book_copy_barcode_active",
            "barcode",
            unique=True,
            sqlite_where=text("deleted_at IS NULL AND barcode IS NOT NULL"),
            postgresql_where=text("deleted_at IS NULL AND barcode IS NOT NULL"),
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", nullable=False, index=True)
    barcode: Optional[str] = Field(default=None, index=True)
    deleted_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
