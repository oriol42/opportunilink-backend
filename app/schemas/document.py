# app/schemas/document.py
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
import uuid


class DocumentResponse(BaseModel):
    """Document data returned by the API."""
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    file_name: str
    file_path: str
    is_valid: bool
    expires_at: Optional[date]
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentVault(BaseModel):
    """
    Summary of the user's document vault.
    Shows which essential docs are present and which are missing.
    """
    documents: list[DocumentResponse]
    has_cv: bool
    has_releve: bool
    has_cni: bool
    has_attestation: bool
    completeness_pct: int   # % of essential docs uploaded
