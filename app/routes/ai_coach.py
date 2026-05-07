# app/routes/ai_coach.py
# AI Coach endpoints — letter generation, future: CV, interview simulator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.database import get_db
from app.models.user import User
from app.models.opportunity import Opportunity
from app.core.dependencies import get_current_user
from app.services.ai_coach import generate_motivation_letter

router = APIRouter()


# --- Request schema ---
# The frontend sends only the opportunity_id.
# We fetch everything else (user profile + opportunity details) from the DB.
# This is safer than letting the frontend send raw profile data.

class LetterRequest(BaseModel):
    opportunity_id: uuid.UUID


# --- Response schema ---

class LetterResponse(BaseModel):
    letter: str
    opportunity_title: str
    word_count: int


# POST /ai/generate-letter
# Generates a personalized motivation letter using Gemini.

@router.post(
    "/generate-letter",
    response_model=LetterResponse,
    status_code=status.HTTP_200_OK,
)
def generate_letter(
    data: LetterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a motivation letter tailored to the user's profile
    and the target opportunity.

    Steps:
    1. Fetch the opportunity from DB (validate it exists).
    2. Call the Gemini service with user + opportunity data.
    3. Return the letter with metadata.
    """
    # Step 1 — Validate opportunity exists
    opp = db.query(Opportunity).filter(
        Opportunity.id == data.opportunity_id,
        Opportunity.is_active == True,
    ).first()

    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found.",
        )

    # Step 2 — Call Gemini
    try:
        letter = generate_motivation_letter(user=current_user, opp=opp)
    except ValueError as e:
        # GEMINI_API_KEY not configured
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except Exception as e:
        # Gemini API error (rate limit, network, etc.)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI service error: {str(e)}",
        )

    # Step 3 — Return letter + metadata
    word_count = len(letter.split())

    return LetterResponse(
        letter=letter,
        opportunity_title=opp.title,
        word_count=word_count,
    )
