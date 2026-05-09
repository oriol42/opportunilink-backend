# app/models/saved.py
# SavedOpportunity — user bookmarks an opportunity without applying.

from sqlalchemy import Column, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import TimeStampedModel


class SavedOpportunity(TimeStampedModel):
    __tablename__ = "saved_opportunities"

    user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    opportunity_id = Column(UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False)

    # Prevent duplicate saves
    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="uq_saved_user_opp"),
    )

    user        = relationship("User",        back_populates="saved_opportunities")
    opportunity = relationship("Opportunity", back_populates="saved_by")

    def __repr__(self):
        return f"<Saved user={self.user_id} opp={self.opportunity_id}>"
