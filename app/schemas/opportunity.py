# app/schemas/opportunity.py
from pydantic import BaseModel, model_validator, Field
from typing import Optional
from datetime import date, datetime
import uuid

from app.services.scoring import DOC_LABELS

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

    # ── Champs "propres" derives du blob IA stocke dans required_docs ──
    # required_docs est le JSONB brut retourne par l'extraction Groq (scoring.py).
    # Ces champs evitent au frontend de devoir parser ce dict lui-meme,
    # et gardent DOC_LABELS comme source unique de verite (pas de duplication FE).
    ai_extracted: bool = False
    application_method: Optional[str] = None   # email / formulaire_en_ligne / courrier / plateforme
    doc_labels: list[str] = []                 # categories de docs traduites en francais lisible
    specific_documents: list[str] = []         # documents nommes explicitement dans la description
    lang_tests: list[str] = []
    requires_recommendation: bool = False
    requires_motivation_letter: bool = True
    has_salary: bool = False
    salary_text: Optional[str] = None

    @model_validator(mode="after")
    def _unpack_ai_extraction(self):
        d = self.required_docs or {}
        self.ai_extracted = bool(d.get("ai_extracted", False))
        self.application_method = d.get("application_method")
        self.doc_labels = [DOC_LABELS.get(c, c) for c in d.get("required_docs", [])]
        self.specific_documents = d.get("specific_documents", [])
        self.lang_tests = d.get("lang_tests", [])
        self.requires_recommendation = bool(d.get("requires_recommendation", False))
        self.requires_motivation_letter = bool(d.get("requires_motivation_letter", True))
        self.has_salary = bool(d.get("has_salary", False))
        self.salary_text = d.get("salary_text")
        return self

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
    min_gpa: Optional[float] = None
    # Scores calculés par le service
    relevance_score: Optional[float] = None
    prep_score: Optional[int] = None

    # required_docs sert uniquement a calculer application_method ci-dessous ;
    # exclude=True pour ne pas alourdir le feed (jusqu a 200 items) avec le blob complet.
    required_docs: dict = Field(default={}, exclude=True)
    ai_extracted: bool = False
    application_method: Optional[str] = None   # email / formulaire_en_ligne / courrier / plateforme
    has_salary: bool = False
    salary_text: Optional[str] = None

    @model_validator(mode="after")
    def _unpack_ai_extraction(self):
        d = self.required_docs or {}
        self.ai_extracted = bool(d.get("ai_extracted", False))
        self.application_method = d.get("application_method")
        self.has_salary = bool(d.get("has_salary", False))
        self.salary_text = d.get("salary_text")
        return self

    model_config = {"from_attributes": True}
