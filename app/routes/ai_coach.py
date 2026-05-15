# app/routes/ai_coach.py — VERSION COMPLÈTE avec /chat
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import uuid

from app.database import get_db
from app.models.user import User
from app.models.opportunity import Opportunity
from app.core.dependencies import get_current_user
from app.services.ai_coach import generate_motivation_letter, generate_cv_advice, chat_with_coach

router = APIRouter()


class LetterRequest(BaseModel):
    opportunity_id: uuid.UUID


class LetterResponse(BaseModel):
    letter: str
    opportunity_title: str
    word_count: int


class CVAdviceResponse(BaseModel):
    titre_cv: str
    resume: str
    competences_a_mettre_en_avant: list[str]
    points_a_valoriser: list[str]
    conseils: list[str]
    opportunity_title: str


class ChatMessage(BaseModel):
    role: str   # "user" ou "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str


# POST /ai/generate-letter

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
        raise HTTPException(status_code=404, detail="Opportunity not found.")

    try:
        letter = generate_motivation_letter(user=current_user, opp=opp)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {str(e)}")

    return LetterResponse(
        letter=letter,
        opportunity_title=opp.title,
        word_count=len(letter.split()),
    )


# POST /ai/generate-cv

@router.post("/generate-cv", response_model=CVAdviceResponse)
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
        raise HTTPException(status_code=404, detail="Opportunity not found.")

    try:
        advice = generate_cv_advice(user=current_user, opp=opp)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {str(e)}")

    return CVAdviceResponse(
        opportunity_title=opp.title,
        **advice,
    )


# POST /ai/chat — Nouveau endpoint manquant !

@router.post("/chat", response_model=ChatResponse)
def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Coach IA conversationnel.
    Reçoit un message + l'historique de la conversation.
    Retourne une réponse contextualisée avec le profil de l'utilisateur.
    """
    try:
        reply = chat_with_coach(
            user=current_user,
            message=data.message,
            history=[{"role": m.role, "content": m.content} for m in data.history],
        )
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {str(e)}")

    return ChatResponse(reply=reply)
