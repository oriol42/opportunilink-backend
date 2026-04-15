# app/schemas/opportunity.py
# Pydantic schemas for Opportunity

from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import date, datetime
import uuid


class OpportunityBase(BaseModel):
    title: str
    type: str           # bourse/stage/emploi/echange/concours
    description: Optional[str] = None
    source_url: Optional[str] = None
    deadline: Optional[date] = None
    country: Optional[str] = None

    # Eligibility
    required_level: list[str] = []
    required_fields: list[str] = []
    required_languages: list[str] = []
    min_gpa: Optional[float] = None
    required_docs: dict = {}


class OpportunityCreate(OpportunityBase):
    """Used when an organization or admin creates an opportunity."""
    organization_id: Optional[uuid.UUID] = None


class OpportunityResponse(OpportunityBase):
    """Full opportunity data returned by the API."""
    id: uuid.UUID
    organization_id: Optional[uuid.UUID]
    reliability_score: int
    is_verified: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class OpportunityFeedItem(BaseModel):
    """
    Lightweight version for the feed — not all fields needed in a list.
    Saves bandwidth and speeds up the frontend rendering.
    """
    id: uuid.UUID
    title: str
    type: str
    country: Optional[str]
    deadline: Optional[date]
    reliability_score: int
    is_verified: bool

    # These come from the scoring service, not directly from DB
    relevance_score: Optional[float] = None
    prep_score: Optional[int] = None

    model_config = {"from_attributes": True}