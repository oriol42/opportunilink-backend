# app/models/user.py
# User model — students and organization members

from sqlalchemy import Column, String, Float, Integer, Boolean, ARRAY
from sqlalchemy.orm import relationship
from app.models.base import TimeStampedModel


class User(TimeStampedModel):
    __tablename__ = "users"

    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)

    # Academic profile
    level = Column(String, nullable=True)   # Licence / Master / Doctorat / BTS
    field = Column(String, nullable=True)   # Informatique, Droit, Médecine...
    city = Column(String, nullable=True)    # Yaoundé, Douala...
    gpa = Column(Float, nullable=True)      # Moyenne / 20

    # Arrays — PostgreSQL native array type
    languages = Column(ARRAY(String), default=list)   # ['fr', 'en', 'de']
    skills = Column(ARRAY(String), default=list)       # ['Python', 'React'...]

    # Contact
    phone = Column(String, nullable=True)  # For SMS alerts

    # Gamification
    opportuni_score = Column(Integer, default=0)  # Score 0-1000

    # Access
    is_premium = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Relationships — tells SQLAlchemy how tables are connected
    applications = relationship("Application", back_populates="user")
    documents = relationship("Document", back_populates="user")
    alerts = relationship("Alert", back_populates="user")
    reports = relationship("Report", back_populates="reporter")

    def __repr__(self):
        return f"<User {self.email}>"