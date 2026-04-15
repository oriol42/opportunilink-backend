# app/models/opportunity.py
# Opportunity model — scholarships, internships, jobs, exchanges, contests

from sqlalchemy import Column, String, Text, Float, Integer, Boolean, Date, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.models.base import TimeStampedModel


class Opportunity(TimeStampedModel):
    __tablename__ = "opportunities"

    title = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False, index=True)  # bourse/stage/emploi/echange/concours
    description = Column(Text, nullable=True)

    # Source
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    source_url = Column(String, nullable=True)

    # Deadline
    deadline = Column(Date, nullable=True, index=True)

    # Eligibility criteria — stored as arrays for flexible matching
    required_level = Column(ARRAY(String), default=list)      # ['Master', 'Doctorat']
    required_fields = Column(ARRAY(String), default=list)     # ['Informatique', 'Droit']
    required_languages = Column(ARRAY(String), default=list)  # ['fr', 'en']
    min_gpa = Column(Float, nullable=True)

    # JSONB — flexible structure for required documents
    # Example: {"required": ["cv", "lettre", "releve"], "optional": ["portfolio"]}
    required_docs = Column(JSONB, default=dict)

    # Destination
    country = Column(String, nullable=True)

    # Trust & Quality
    reliability_score = Column(Integer, default=50)  # 0-100, set by anti-scam pipeline
    is_verified = Column(Boolean, default=False)

    # Source tracking
    is_scraped = Column(Boolean, default=False)   # True = came from crawler
    is_active = Column(Boolean, default=True)     # False = expired or removed

    # Relationships
    organization = relationship("Organization", back_populates="opportunities")
    applications = relationship("Application", back_populates="opportunity")
    alerts = relationship("Alert", back_populates="opportunity")
    reports = relationship("Report", back_populates="opportunity")

    def __repr__(self):
        return f"<Opportunity {self.title[:50]}>"