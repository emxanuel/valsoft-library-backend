from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters long.")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class LoginResponse(BaseModel):
    user: UserRead

