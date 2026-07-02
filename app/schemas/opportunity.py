# app/schemas/opportunity.py
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
import uuid

class OpportunityBase(BaseModel):
    title: str
    type: str
    description: Optional[str] = None
    source_url: Optional[str] = None
    deadline: Optional[date] = None
    country: Optional[str] = None
    required_level: list[str] = []
    required_fields: list[str] = []
    required_languages: list[str] = []
    min_gpa: Optional[float] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    required_docs: dict = {}

class OpportunityCreate(OpportunityBase):
    organization_id: Optional[uuid.UUID] = None

class OpportunityResponse(OpportunityBase):
    id: uuid.UUID
    organization_id: Optional[uuid.UUID]
    reliability_score: int
    is_verified: bool
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class OpportunityFeedItem(BaseModel):
    id: uuid.UUID
    title: str
    type: str
    country: Optional[str] = None
    deadline: Optional[date] = None
    reliability_score: int = 50
    is_verified: bool = False
    # Champs nécessaires pour le matching côté frontend
    description: Optional[str] = None
    source_url: Optional[str] = None
    required_fields: list[str] = []
    required_level: list[str] = []
    required_languages: list[str] = []
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    # Scores calculés par le service
    relevance_score: Optional[float] = None
    prep_score: Optional[int] = None
    model_config = {"from_attributes": True}
