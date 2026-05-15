# app/routes/organizations.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date
import uuid

from app.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.models.opportunity import Opportunity
from app.models.application import Application
from app.schemas.opportunity import OpportunityResponse
from app.core.dependencies import get_current_user
from app.services.cache import cache_delete_pattern

router = APIRouter()

class OrgCreate(BaseModel):
    name: str
    type: Optional[str] = None
    domain: Optional[str] = None
    website: Optional[str] = None

class OrgResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: Optional[str]
    domain: Optional[str]
    website: Optional[str]
    is_verified: bool
    plan: str
    model_config = {"from_attributes": True}

class OrgOpportunityCreate(BaseModel):
    title: str
    type: str
    description: str
    country: Optional[str] = "Cameroun"
    deadline: Optional[date] = None
    source_url: Optional[str] = None
    required_level: list[str] = []
    required_fields: list[str] = []
    required_languages: list[str] = ["fr"]
    min_gpa: Optional[float] = None
    required_docs: dict = {}

class ToggleStatus(BaseModel):
    is_active: bool

class AnalyticsResponse(BaseModel):
    total_opportunities: int
    active_opportunities: int
    total_applications: int
    applications_by_status: dict
    top_opportunity: Optional[str]

@router.post("/register", response_model=OrgResponse, status_code=201)
def register_organization(data: OrgCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = Organization(name=data.name, type=data.type, domain=data.domain, website=data.website, is_verified=False, plan="free")
    db.add(org); db.commit(); db.refresh(org)
    return org

@router.get("/me", response_model=OrgResponse)
def get_my_organization(org_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org: raise HTTPException(status_code=404, detail="Organization not found")
    return org

@router.post("/opportunities", response_model=OpportunityResponse, status_code=201)
def publish_opportunity(data: OrgOpportunityCreate, org_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org: raise HTTPException(status_code=404, detail="Organization not found")
    if data.deadline and data.deadline < date.today(): raise HTTPException(status_code=400, detail="Deadline must be in the future")
    opp = Opportunity(title=data.title, type=data.type, description=data.description, country=data.country, deadline=data.deadline, source_url=data.source_url, required_level=data.required_level, required_fields=data.required_fields, required_languages=data.required_languages, min_gpa=data.min_gpa, required_docs=data.required_docs, organization_id=org_id, is_scraped=False, is_active=True, reliability_score=80)
    db.add(opp); db.commit(); db.refresh(opp)
    cache_delete_pattern("feed:user:*")
    try:
        from app.tasks.alert_tasks import create_alerts_for_opportunity
        create_alerts_for_opportunity.delay(str(opp.id))
    except Exception: pass
    return opp

@router.patch("/opportunities/{opportunity_id}", status_code=200)
def toggle_opportunity_status(org_id: uuid.UUID, opportunity_id: uuid.UUID, data: ToggleStatus, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id, Opportunity.organization_id == org_id).first()
    if not opp: raise HTTPException(status_code=404, detail="Opportunity not found")
    opp.is_active = data.is_active
    db.commit()
    cache_delete_pattern("feed:user:*")
    return {"id": str(opp.id), "is_active": opp.is_active}

@router.get("/opportunities", response_model=list[OpportunityResponse])
def get_org_opportunities(org_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Opportunity).filter(Opportunity.organization_id == org_id).order_by(Opportunity.created_at.desc()).all()

@router.get("/analytics", response_model=AnalyticsResponse)
def get_org_analytics(org_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opps = db.query(Opportunity).filter(Opportunity.organization_id == org_id).all()
    opp_ids = [o.id for o in opps]
    active = sum(1 for o in opps if o.is_active)
    all_apps = db.query(Application).filter(Application.opportunity_id.in_(opp_ids)).all() if opp_ids else []
    by_status = {"draft":sum(1 for a in all_apps if a.status=="draft"), "submitted":sum(1 for a in all_apps if a.status=="submitted"), "accepted":sum(1 for a in all_apps if a.status=="accepted"), "rejected":sum(1 for a in all_apps if a.status=="rejected")}
    top_opp = None
    if opp_ids:
        from sqlalchemy import func
        top = db.query(Opportunity.title, func.count(Application.id).label("cnt")).join(Application, Application.opportunity_id==Opportunity.id, isouter=True).filter(Opportunity.organization_id==org_id).group_by(Opportunity.title).order_by(func.count(Application.id).desc()).first()
        if top: top_opp = top[0]
    return AnalyticsResponse(total_opportunities=len(opps), active_opportunities=active, total_applications=len(all_apps), applications_by_status=by_status, top_opportunity=top_opp)

@router.delete("/opportunities/{opportunity_id}", status_code=204)
def deactivate_opportunity(org_id: uuid.UUID, opportunity_id: uuid.UUID, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id==opportunity_id, Opportunity.organization_id==org_id).first()
    if not opp: raise HTTPException(status_code=404, detail="Opportunity not found")
    opp.is_active = False; db.commit()
    cache_delete_pattern("feed:user:*")
