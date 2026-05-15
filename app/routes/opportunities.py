from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
import uuid

from app.database import get_db
from app.models.user import User
from app.models.opportunity import Opportunity
from app.models.saved import SavedOpportunity
from app.schemas.opportunity import OpportunityCreate, OpportunityResponse, OpportunityFeedItem
from app.core.dependencies import get_current_user
from app.services.matching import build_personalized_feed
from app.services.scoring import compute_preparation_score
from app.services.cache import cache_get, cache_set, cache_delete_pattern

router = APIRouter()

# ─────────────────────────────────────────────────────────────────
# IMPORTANT: routes statiques AVANT routes dynamiques ({id})
# ─────────────────────────────────────────────────────────────────

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
    cache_key = (
        f"feed:user:{current_user.id}"
        f":page:{page}:limit:{limit}"
        f":type:{type}:country:{country}:search:{search}"
    )
    cached = cache_get(cache_key)
    if cached:
        return cached

    query = db.query(Opportunity).filter(Opportunity.is_active == True)
    if type:
        query = query.filter(Opportunity.type == type)
    if country:
        query = query.filter(Opportunity.country.ilike(country))
    if search:
        query = query.filter(Opportunity.title.ilike(f"%{search}%"))

    ranked = build_personalized_feed(
        user=current_user,
        opportunities=query.all(),
        page=page,
        limit=limit,
        db=db,
    )

    result = []
    for opp, score in ranked:
        item = OpportunityFeedItem.model_validate(opp)
        item.relevance_score = score
        result.append(item)

    cache_set(cache_key, [i.model_dump(mode="json") for i in result], ttl_seconds=300)
    return result


# ── ROUTE STATIQUE: /saved — DOIT être AVANT /{opportunity_id} ──
@router.get("/saved", response_model=list[OpportunityFeedItem])
def get_saved_opportunities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retourne toutes les opportunités sauvegardées par l'utilisateur.
    Importante: route statique avant /{id} pour éviter le conflit de routing FastAPI.
    """
    saved = db.query(SavedOpportunity).filter(
        SavedOpportunity.user_id == current_user.id
    ).all()

    if not saved:
        return []

    opp_ids = [s.opportunity_id for s in saved]
    opps = db.query(Opportunity).filter(
        Opportunity.id.in_(opp_ids),
        Opportunity.is_active == True,
    ).all()

    # Ajouter un relevance_score neutre pour les favoris
    result = []
    for opp in opps:
        item = OpportunityFeedItem.model_validate(opp)
        item.relevance_score = None
        result.append(item)

    return result


# ── ROUTES DYNAMIQUES (après les routes statiques) ───────────────

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
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


@router.get("/{opportunity_id}/prep-score")
def get_prep_score(
    opportunity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return compute_preparation_score(user=current_user, opp=opp, db=db)


@router.post("/{opportunity_id}/save", status_code=status.HTTP_200_OK)
def toggle_save(
    opportunity_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Toggle save/unsave d'une opportunité.
    Si déjà sauvegardée → retire des favoris.
    Si pas sauvegardée → ajoute aux favoris.
    Retourne {"saved": bool} pour que le frontend mette à jour l'UI.
    """
    # Chercher si déjà sauvegardé
    existing = db.query(SavedOpportunity).filter(
        SavedOpportunity.user_id == current_user.id,
        SavedOpportunity.opportunity_id == opportunity_id,
    ).first()

    if existing:
        # Déjà sauvegardé → on retire
        db.delete(existing)
        db.commit()
        cache_delete_pattern(f"feed:user:{current_user.id}*")
        return {"saved": False, "message": "Retiré des favoris"}

    # Pas encore sauvegardé → vérifier que l'opportunité existe
    opp = db.query(Opportunity).filter(
        Opportunity.id == opportunity_id,
        Opportunity.is_active == True,
    ).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    # Ajouter aux favoris
    try:
        saved = SavedOpportunity(
            user_id=current_user.id,
            opportunity_id=opportunity_id,
        )
        db.add(saved)
        db.commit()
        cache_delete_pattern(f"feed:user:{current_user.id}*")
        return {"saved": True, "message": "Ajouté aux favoris"}
    except IntegrityError:
        # Race condition — déjà sauvegardé entre la vérification et l'insert
        db.rollback()
        return {"saved": True, "message": "Déjà sauvegardé"}


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
    cache_delete_pattern("feed:user:*")
    try:
        from app.tasks.alert_tasks import create_alerts_for_opportunity
        create_alerts_for_opportunity.delay(str(opp.id))
    except Exception:
        pass
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
    db.add(Report(
        opportunity_id=opportunity_id,
        reported_by=current_user.id,
        reason=reason,
    ))
    db.commit()
    return {"message": "Signalement soumis."}
