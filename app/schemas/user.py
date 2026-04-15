# app/schemas/user.py
# Pydantic schemas for User — defines what the API receives and returns

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import uuid


# ================================
# BASE — shared fields
# ================================

class UserBase(BaseModel):
    """Fields shared across multiple schemas — avoids repetition."""
    email: EmailStr
    full_name: str


# ================================
# INPUT schemas — what the API receives
# ================================

class UserRegister(UserBase):
    """
    Data required to create a new account.
    Password is plain text here — we hash it in the route handler.
    """
    password: str

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    """Data required to log in."""
    email: EmailStr
    password: str


class UserProfileUpdate(BaseModel):
    """
    All fields optional — user can update any subset of their profile.
    This pattern is called a PATCH schema.
    """
    full_name: Optional[str] = None
    level: Optional[str] = None       # Licence / Master / Doctorat / BTS
    field: Optional[str] = None       # Informatique, Droit...
    city: Optional[str] = None
    gpa: Optional[float] = None
    phone: Optional[str] = None
    languages: Optional[list[str]] = None
    skills: Optional[list[str]] = None

    @field_validator("gpa")
    @classmethod
    def gpa_must_be_valid(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0 <= v <= 20):
            raise ValueError("GPA must be between 0 and 20")
        return v


# ================================
# OUTPUT schemas — what the API returns
# ================================

class UserResponse(UserBase):
    """
    Safe user data returned by the API.
    Notice: NO hashed_password field — never exposed.
    """
    id: uuid.UUID
    level: Optional[str]
    field: Optional[str]
    city: Optional[str]
    gpa: Optional[float]
    phone: Optional[str]
    languages: list[str] = []
    skills: list[str] = []
    opportuni_score: int
    is_premium: bool
    created_at: datetime

    # This tells Pydantic to read data from SQLAlchemy model attributes
    # Without this, Pydantic wouldn't know how to read ORM objects
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Returned after successful login or register."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse