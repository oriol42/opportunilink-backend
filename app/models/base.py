# app/models/base.py
# Shared base model — all models inherit from this

import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class TimeStampedModel(Base):
    """
    Abstract base class that adds id + timestamps to every model.
    'abstract = True' means SQLAlchemy won't create a table for this class.
    It's just a blueprint for other models to inherit from.
    """
    __abstract__ = True

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,   
        index=True,
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,  
        nullable=False,
    )