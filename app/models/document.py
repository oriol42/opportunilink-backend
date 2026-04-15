# app/models/document.py
# Document vault — student's uploaded files (CV, transcripts, ID...)

from sqlalchemy import Column, String, Boolean, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import TimeStampedModel


class Document(TimeStampedModel):
    __tablename__ = "documents"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    type = Column(String, nullable=False)          # cni/releve/attestation/cv/photo/autre
    file_path = Column(String, nullable=False)     # Path in Supabase Storage
    file_name = Column(String, nullable=False)     # Original filename

    is_valid = Column(Boolean, default=True)       # Not expired
    expires_at = Column(Date, nullable=True)       # Optional expiry (e.g. passport)

    # Relationships
    user = relationship("User", back_populates="documents")

    def __repr__(self):
        return f"<Document {self.type} — {self.file_name}>"