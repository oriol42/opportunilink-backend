# app/routes/opportunities.py
# Opportunity endpoints — feed, detail, prep score, save, report

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from app.database import get_db
from app.models.user import User
from app.models.opportunity import Opportunity
from app.schemas.opportunity import (
    OpportunityCreate,
    OpportunityResponse,
    OpportunityFeedItem,
)
from app.core.dependencies import get_current_user
from app.services.matching import build_personalized_feed, compute_relevance_score
from app.services.scoring import compute_preparation_score

router = APIRouter()



# GET /opportunities — Personalized feed


@router.get("", response_model=list[OpportunityFeedItem])
def get_feed(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    type: Optional[str] = Query(None),        # Filter by type
    country: Optional[str] = Query(None),     # Filter by country
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns a personalized, ranked feed of opportunities.

    The feed is sorted by relevance score (computed by matching.py).
    Optional filters: type (bourse/stage/emploi...), country.

    Pagination: page + limit query params.
    """
    # Fetch all active opportunities
    query = db.query(Opportunity).filter(Opportunity.is_active == True)

    # Apply optional filters
    if type:
        query = query.filter(Opportunity.type == type)
    if country:
        query = query.filter(Opportunity.country == country)

    opportunities = query.all()

    # Score and rank using the matching algorithm
    ranked = build_personalized_feed(
        user=current_user,
        opportunities=opportunities,
        page=page,
        limit=limit,
    )

    # Build response — add relevance_score to each item
    result = []
    for opp, score in ranked:
        item = OpportunityFeedItem.model_validate(opp)
        item.relevance_score = score
        result.append(item)

    return result


# GET /opportunities/{id} — Opportunity detail


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(
    opportunity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the full detail of a single opportunity."""
    opp = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
        Opportunity.is_active == True,
    ).first()

    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    return opp


# GET /opportunities/{id}/prep-score — Preparation score


@router.get("/{opportunity_id}/prep-score")
def get_prep_score(
    opportunity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the user's preparation score for a specific opportunity.
    Shows what's missing and what to do to be ready.
    This is the key feature that differentiates OpportuLink.
    """
    opp = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
    ).first()

    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Opportunity not found",
        )

    return compute_preparation_score(
        user=current_user,
        opp=opp,
        db=db,
    )



# POST /opportunities — Create opportunity (admin/org)


@router.post("", response_model=OpportunityResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    data: OpportunityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates a new opportunity.
    For now: any authenticated user can create one (for testing).
    In Phase 2: restricted to verified organizations and admins.
    """
    opp = Opportunity(**data.model_dump())
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp

# POST /opportunities/{id}/report — Report an opportunity


@router.post("/{opportunity_id}/report", status_code=status.HTTP_201_CREATED)
def report_opportunity(
    opportunity_id: uuid.UUID,
    reason: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reports an opportunity as suspicious, expired, or fraudulent.
    The report is stored and reviewed by the moderation team.
    """
    from app.models.report import Report

    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    report = Report(
        opportunity_id=opportunity_id,
        reported_by=current_user.id,
        reason=reason,
    )
    db.add(report)
    db.commit()

    return {"message": "Report submitted. Thank you for helping keep OpportuLink safe."}
