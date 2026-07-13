# app/models/user.py
# User model — students and organization members

from sqlalchemy import Column, String, Float, Integer, Boolean, ARRAY, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.models.base import TimeStampedModel


class User(TimeStampedModel):
    __tablename__ = "users"

    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)

    # Academic profile
    level = Column(String, nullable=True)   # Bac / Licence / Master / Doctorat / BTS
    field = Column(String, nullable=True)   # Informatique, Droit, Médecine...
    city = Column(String, nullable=True)    # Yaoundé, Douala...
    gpa = Column(Float, nullable=True)      # Moyenne / 20
    age = Column(Integer, nullable=True)    # Nécessaire pour filtrer les opportunités avec limite d'âge
    gender = Column(String, nullable=True)  # 'homme' / 'femme' — optionnel, auto-déclaré,
                                              # sert uniquement pour les opportunités reservées a un genre

    # Arrays — PostgreSQL native array type
    languages = Column(ARRAY(String), default=list)   # ['fr', 'en', 'de']
    skills = Column(ARRAY(String), default=list)       # ['Python', 'React'...]
    objectives = Column(ARRAY(String), default=list)   # ['bourse', 'stage'...]

    # JSONB — niveau de maîtrise par compétence, ex: {"Python": 75, "React": 50}
    skills_with_level = Column(JSONB, default=dict)

    # Contact
    phone = Column(String, nullable=True)  # For SMS alerts

    # Lien vers l'organisation que cet utilisateur gère (module B2B).
    # NULL pour 99% des étudiants. Utilisé pour vérifier côté serveur
    # qu'un utilisateur n'accède qu'à SA PROPRE organisation (corrige
    # une faille où org_id était accepté sans aucune vérification).
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)

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
    saved_opportunities = relationship("SavedOpportunity", back_populates="user")

    def __repr__(self):
        return f"<User {self.email}>"