# app/models/alert.py
# Alerts — deadline reminders and new match notifications

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import TimeStampedModel


class Alert(TimeStampedModel):
    __tablename__ = "alerts"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False)

    type = Column(String, nullable=False)      # j7 / j1 / new_match
    channel = Column(String, nullable=False)   # sms / email / push

    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="alerts")
    opportunity = relationship("Opportunity", back_populates="alerts")

    def __repr__(self):
        return f"<Alert {self.type} → {self.channel} sent={self.is_sent}>"