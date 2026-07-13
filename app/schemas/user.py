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
    level: Optional[str] = None       # Bac / Licence / Master / Doctorat / BTS
    field: Optional[str] = None       # Informatique, Droit...
    city: Optional[str] = None
    gpa: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None      # 'homme' / 'femme' — optionnel
    phone: Optional[str] = None
    languages: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    objectives: Optional[list[str]] = None
    skills_with_level: Optional[dict[str, int]] = None

    @field_validator("age")
    @classmethod
    def age_must_be_realistic(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (14 <= v <= 100):
            raise ValueError("Age must be between 14 and 100")
        return v

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
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str]
    languages: list[str] = []
    skills: list[str] = []
    objectives: list[str] = []
    skills_with_level: dict[str, int] = {}
    organization_id: Optional[uuid.UUID] = None
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