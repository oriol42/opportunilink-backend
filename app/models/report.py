# app/models/report.py
# Reports — anti-scam flagging by users

from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import TimeStampedModel


class Report(TimeStampedModel):
    __tablename__ = "reports"

    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False, index=True)
    reported_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    reason = Column(String, nullable=False)    # arnaque/lien_mort/info_fausse/expire
    details = Column(Text, nullable=True)      # Optional explanation

    resolved = Column(Boolean, default=False)  # Reviewed by moderation team

    # Relationships
    opportunity = relationship("Opportunity", back_populates="reports")
    reporter = relationship("User", back_populates="reports")

    def __repr__(self):
        return f"<Report {self.reason} resolved={self.resolved}>"