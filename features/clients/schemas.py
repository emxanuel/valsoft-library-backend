from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ClientCheckout(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    phone: Optional[str] = None


class ClientCreate(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)
    phone: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    email: Optional[str] = Field(default=None, min_length=1)
    phone: Optional[str] = None


class ClientRead(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    created_at: datetime
    updated_at: datetime


class ClientListPage(BaseModel):
    items: list[ClientRead]
    total: int
    limit: int
    offset: int
