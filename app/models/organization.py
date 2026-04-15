# app/models/organization.py
# Organizations — universities, companies, NGOs, embassies

from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import relationship
from app.models.base import TimeStampedModel


class Organization(TimeStampedModel):
    __tablename__ = "organizations"

    name = Column(String, nullable=False)
    type = Column(String, nullable=True)     # université/entreprise/ong/ambassade
    domain = Column(String, nullable=True)   # Official email domain for verification
    website = Column(String, nullable=True)

    is_verified = Column(Boolean, default=False)
    plan = Column(String, default="free")    # free/starter/pro/enterprise

    # Relationships
    opportunities = relationship("Opportunity", back_populates="organization")

    def __repr__(self):
        return f"<Organization {self.name}>"