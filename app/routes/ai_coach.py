from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import date

from app.database import get_db
from app.models.user import User
from app.models.opportunity import Opportunity
from app.models.application import Application
from app.models.document import Document
from app.core.dependencies import get_current_user
from app.services.ai_coach import generate_motivation_letter, generate_cv_advice, chat_with_coach
from app.services.matching import pre_filter_opportunities, build_personalized_feed

router = APIRouter()


class LetterRequest(BaseModel):
    opportunity_id: uuid.UUID


class LetterResponse(BaseModel):
    letter: str
    opportunity_title: str
    word_count: int


class FormationItem(BaseModel):
    periode: str
    titre: str
    etablissement: str


class LangueItem(BaseModel):
    langue: str
    niveau: str


class CVResponse(BaseModel):
    titre_accroche: str
    resume_profil: str
    formation: list[FormationItem]
    competences_techniques: list[str]
    competences_transverses: list[str]
    langues: list[LangueItem]
    points_forts: list[str]
    conseils_amelioration: list[str]
    opportunity_title: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []
    # NOTE : le contexte (profil + opportunités) est désormais construit
    # côté serveur à partir du VRAI feed personnalisé de l'utilisateur —
    # un éventuel champ "context" envoyé par le frontend est ignoré
    # volontairement pour éviter toute divergence entre deux sources de vérité.


class ChatResponse(BaseModel):
    reply: str


@router.post("/generate-letter", response_model=LetterResponse)
def generate_letter(
    data: LetterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opp = db.query(Opportunity).filter(
        Opportunity.id == data.opportunity_id,
        Opportunity.is_active == True,
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunité introuvable.")
    try:
        letter = generate_motivation_letter(user=current_user, opp=opp)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur IA : {str(e)}")

    return LetterResponse(letter=letter, opportunity_title=opp.title, word_count=len(letter.split()))


@router.post("/generate-cv", response_model=CVResponse)
def generate_cv(
    data: LetterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opp = db.query(Opportunity).filter(
        Opportunity.id == data.opportunity_id,
        Opportunity.is_active == True,
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunité introuvable.")
    try:
        cv_data = generate_cv_advice(user=current_user, opp=opp)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur IA : {str(e)}")

    return CVResponse(opportunity_title=opp.title, **cv_data)


@router.post("/chat", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Coach IA avec contexte complet :
    - Profil utilisateur
    - Ses VRAIES opportunités personnalisées (mêmes que son feed, pas un tri générique)
    - Ses documents manquants
    - Son nombre de candidatures
    """
    # On réutilise exactement la même logique que le feed principal
    # (pre_filter + scoring de pertinence), pour que le coach IA parle
    # des mêmes opportunités que celles que l'étudiant voit réellement.
    candidates = pre_filter_opportunities(current_user, db)
    ranked = build_personalized_feed(current_user, candidates, page=1, limit=15, db=db)
    opps = [opp for opp, score in ranked]

    # Documents existants
    existing_doc_types = {
        d.type for d in db.query(Document.type)
        .filter(Document.user_id == current_user.id)
        .all()
    }
    essential_docs = ["cni", "releve", "attestation", "cv"]
    missing_docs = [d for d in essential_docs if d not in existing_doc_types]

    # Candidatures
    apps_count = db.query(Application).filter(
        Application.user_id == current_user.id
    ).count()

    # Calcul profil %
    fields = [
        current_user.level, current_user.field, current_user.city,
        current_user.gpa, current_user.phone,
        bool(current_user.skills), bool(current_user.languages),
    ]
    profile_pct = round(sum(1 for f in fields if f) / len(fields) * 100)

    context_data = {
        "missing_docs": missing_docs,
        "applications_count": apps_count,
        "profile_pct": profile_pct,
    }

    try:
        reply = chat_with_coach(
            user=current_user,
            message=data.message,
            history=[{"role": m.role, "content": m.content} for m in data.history],
            opportunities=opps,
            context_data=context_data,
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur IA : {str(e)}")

    return ChatResponse(reply=reply)
