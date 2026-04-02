from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from features.auth.schemas import UserRoleSchema


class EmployeeCreate(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1)
    last_name: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    role: UserRoleSchema | None = None


class StaffRead(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    role: UserRoleSchema
    created_at: datetime
    updated_at: datetime


class StaffListPage(BaseModel):
    items: list[StaffRead]
    total: int
    limit: int
    offset: int
