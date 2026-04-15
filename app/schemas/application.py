# app/schemas/application.py
# Pydantic schemas for Application

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


class ApplicationCreate(BaseModel):
    """Data needed to start a new application."""
    opportunity_id: uuid.UUID
    notes: Optional[str] = None


class ApplicationUpdate(BaseModel):
    """Update status or notes — all optional."""
    status: Optional[str] = None    # draft/submitted/accepted/rejected
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None


class ApplicationResponse(BaseModel):
    """Full application data returned by the API."""
    id: uuid.UUID
    user_id: uuid.UUID
    opportunity_id: uuid.UUID
    status: str
    prep_score: Optional[int]
    missing_items: list = []
    generated_letter: Optional[str]
    notes: Optional[str]
    applied_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}