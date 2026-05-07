# app/routes/opportunities.py
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
from app.services.matching import build_personalized_feed
from app.services.scoring import compute_preparation_score

router = APIRouter()

@router.get("", response_model=list[OpportunityFeedItem])
def get_feed(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    type: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Opportunity).filter(Opportunity.is_active == True)
    if type:
        query = query.filter(Opportunity.type == type)
    if country:
        query = query.filter(Opportunity.country.ilike(country))
    if search:
        query = query.filter(Opportunity.title.ilike(f"%{search}%"))
    opportunities = query.all()
    ranked = build_personalized_feed(
        user=current_user,
        opportunities=opportunities,
        page=page,
        limit=limit,
    )
    result = []
    for opp, score in ranked:
        item = OpportunityFeedItem.model_validate(opp)
        item.relevance_score = score
        result.append(item)
    return result

@router.get("/{opportunity_id}", response_model=OpportunityResponse)
def get_opportunity(
    opportunity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opp = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
        Opportunity.is_active == True,
    ).first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return opp

@router.get("/{opportunity_id}/prep-score")
def get_prep_score(
    opportunity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")
    return compute_preparation_score(user=current_user, opp=opp, db=db)

@router.post("", response_model=OpportunityResponse, status_code=status.HTTP_201_CREATED)
def create_opportunity(
    data: OpportunityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opp = Opportunity(**data.model_dump())
    db.add(opp)
    db.commit()
    db.refresh(opp)

    # Trigger alert creation for eligible users (async, non-blocking)
    try:
        from app.tasks.alert_tasks import create_alerts_for_opportunity
        create_alerts_for_opportunity.delay(str(opp.id))
    except Exception as e:
        # If Celery/Redis is unavailable, log and continue — don't fail the request
        import logging
        logging.getLogger(__name__).warning(f"Could not enqueue alert task: {e}")

    return opp

@router.post("/{opportunity_id}/report", status_code=status.HTTP_201_CREATED)
def report_opportunity(
    opportunity_id: uuid.UUID,
    reason: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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
