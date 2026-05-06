# app/routes/applications.py
# Application endpoints — list, create, update status, delete

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import uuid

from app.database import get_db
from app.models.user import User
from app.models.application import Application
from app.models.opportunity import Opportunity
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.core.dependencies import get_current_user

router = APIRouter()


# --- Response schema that includes opportunity details ---
# We define it here instead of schemas/application.py because it's
# specific to this endpoint and joins two tables.

class OpportunitySnapshot(BaseModel):
    """Minimal opportunity info embedded in the application response."""
    id: uuid.UUID
    title: str
    type: str
    country: str
    deadline: Optional[date]

class ApplicationWithOpportunity(BaseModel):
    """Application + its opportunity details in one response."""
    id: uuid.UUID
    opportunity_id: uuid.UUID
    status: str
    notes: Optional[str]
    prep_score: Optional[int]
    applied_at: Optional[datetime]
    created_at: datetime
    opportunity: OpportunitySnapshot

    model_config = {"from_attributes": True}


# GET /applications — list all applications for current user

@router.get("", response_model=list[ApplicationWithOpportunity])
def get_my_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns all applications for the authenticated user,
    sorted by most recent first, with opportunity details included.

    joinedload() tells SQLAlchemy to fetch the related opportunity
    in the same query (SQL JOIN) instead of N separate queries.
    """
    applications = (
        db.query(Application)
        .options(joinedload(Application.opportunity))  # Eager load opportunity
        .filter(Application.user_id == current_user.id)
        .order_by(Application.created_at.desc())
        .all()
    )

    result = []
    for app in applications:
        result.append(ApplicationWithOpportunity(
            id=app.id,
            opportunity_id=app.opportunity_id,
            status=app.status,
            notes=app.notes,
            prep_score=app.prep_score,
            applied_at=app.applied_at,
            created_at=app.created_at,
            opportunity=OpportunitySnapshot(
                id=app.opportunity.id,
                title=app.opportunity.title,
                type=app.opportunity.type,
                country=app.opportunity.country,
                deadline=app.opportunity.deadline,
            ),
        ))

    return result


# POST /applications — start a new application

@router.post("", response_model=ApplicationWithOpportunity, status_code=status.HTTP_201_CREATED)
def create_application(
    data: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a new application in 'draft' status."""
    # Check opportunity exists
    opp = db.query(Opportunity).filter(Opportunity.id == data.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    # Prevent duplicate applications
    existing = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.opportunity_id == data.opportunity_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Application already exists")

    app = Application(
        user_id=current_user.id,
        opportunity_id=data.opportunity_id,
        notes=data.notes,
        status="draft",
    )
    db.add(app)
    db.commit()
    db.refresh(app)

    # Reload with relationship
    app = (
        db.query(Application)
        .options(joinedload(Application.opportunity))
        .filter(Application.id == app.id)
        .first()
    )

    return ApplicationWithOpportunity(
        id=app.id,
        opportunity_id=app.opportunity_id,
        status=app.status,
        notes=app.notes,
        prep_score=app.prep_score,
        applied_at=app.applied_at,
        created_at=app.created_at,
        opportunity=OpportunitySnapshot(
            id=app.opportunity.id,
            title=app.opportunity.title,
            type=app.opportunity.type,
            country=app.opportunity.country,
            deadline=app.opportunity.deadline,
        ),
    )


# PUT /applications/{id} — update status or notes

@router.put("/{application_id}", response_model=ApplicationWithOpportunity)
def update_application(
    application_id: uuid.UUID,
    data: ApplicationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates status or notes on an application."""
    app = (
        db.query(Application)
        .options(joinedload(Application.opportunity))
        .filter(
            Application.id == application_id,
            Application.user_id == current_user.id,
        )
        .first()
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if data.status:
        app.status = data.status
        # Record submission date when status becomes "submitted"
        if data.status == "submitted" and not app.applied_at:
            app.applied_at = datetime.utcnow()
    if data.notes is not None:
        app.notes = data.notes

    db.commit()
    db.refresh(app)

    return ApplicationWithOpportunity(
        id=app.id,
        opportunity_id=app.opportunity_id,
        status=app.status,
        notes=app.notes,
        prep_score=app.prep_score,
        applied_at=app.applied_at,
        created_at=app.created_at,
        opportunity=OpportunitySnapshot(
            id=app.opportunity.id,
            title=app.opportunity.title,
            type=app.opportunity.type,
            country=app.opportunity.country,
            deadline=app.opportunity.deadline,
        ),
    )


# DELETE /applications/{id} — remove an application

@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes an application. Only the owner can delete."""
    app = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    db.delete(app)
    db.commit()
