# app/routes/applications.py
# NOUVEAU : candidature intelligente
# Detecte comment postuler et agit en consequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import uuid
import re

from app.database import get_db
from app.models.user import User
from app.models.application import Application
from app.models.opportunity import Opportunity
from app.models.document import Document
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.core.dependencies import get_current_user

router = APIRouter()


class OpportunitySnapshot(BaseModel):
    id: uuid.UUID
    title: str
    type: str
    country: str
    deadline: Optional[date]


class ApplicationWithOpportunity(BaseModel):
    id: uuid.UUID
    opportunity_id: uuid.UUID
    status: str
    notes: Optional[str]
    prep_score: Optional[int]
    applied_at: Optional[datetime]
    created_at: datetime
    opportunity: OpportunitySnapshot
    model_config = {"from_attributes": True}


class ApplyResponse(BaseModel):
    """Reponse intelligente au bouton Postuler"""
    application_id: uuid.UUID
    method: str           # "external_link" | "email" | "direct"
    action_url: Optional[str]   # lien externe ou mailto
    message: str
    ready: bool           # True si dossier complet


def detect_application_method(opp: Opportunity) -> dict:
    """
    Detecte comment postuler a cette opportunite.
    Retourne : method, action_url, contact_email
    """
    source = opp.source_url or ""
    desc = (opp.description or "").lower()
    title = (opp.title or "").lower()

    # Chercher un email de contact dans la description
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, opp.description or "")
    # Filtrer les emails generiques non pertinents
    contact_email = None
    for email in emails:
        if not any(x in email for x in ["example", "exemple", "test", "noreply"]):
            contact_email = email
            break

    # Detecter plateformes avec formulaire en ligne
    online_platforms = [
        "daad.de", "campus france", "auf.org", "erasmus",
        "opportunitydesk.org", "remotive.com", "themuse.com",
        "reliefweb.int", "euraxess", "scholars4dev",
        "linkedin.com", "indeed.com", "glassdoor",
    ]
    is_online_platform = any(p in source.lower() for p in online_platforms)

    # Detecter si candidature par email
    email_keywords = ["envoyer", "envoie", "soumettre par email", "postuler par email",
                      "send your", "submit by email", "candidature par courrier"]
    is_email_apply = any(kw in desc for kw in email_keywords)

    if is_email_apply and contact_email:
        return {
            "method": "email",
            "action_url": f"mailto:{contact_email}",
            "contact_email": contact_email,
        }
    elif is_online_platform or source:
        return {
            "method": "external_link",
            "action_url": source,
            "contact_email": None,
        }
    else:
        return {
            "method": "external_link",
            "action_url": source,
            "contact_email": contact_email,
        }


def check_user_readiness(user: User, opp: Opportunity, db: Session) -> dict:
    """
    Verifie si l etudiant a les documents essentiels.
    Retourne un resumé de ce qui est pret et ce qui manque.
    """
    docs = db.query(Document).filter(
        Document.user_id == user.id,
        Document.is_valid == True,
    ).all()
    doc_types = {d.type for d in docs}

    required_docs = []
    if opp.required_docs and opp.required_docs.get("required_docs"):
        required_docs = opp.required_docs["required_docs"]
    else:
        required_docs = ["cv", "releve"]

    # Filtrer les docs qu on peut verifier dans le coffre fort
    checkable = [d for d in required_docs
                 if d not in ("lettre_motivation", "lettre_recommandation")]

    missing = [d for d in checkable if d not in doc_types]
    ready = len(missing) == 0

    return {
        "ready": ready,
        "missing_docs": missing,
        "available_docs": list(doc_types),
    }


# GET /applications

@router.get("", response_model=list[ApplicationWithOpportunity])
def get_my_applications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    applications = (
        db.query(Application)
        .options(joinedload(Application.opportunity))
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


# POST /applications — Candidature intelligente

@router.post("", response_model=ApplicationWithOpportunity, status_code=status.HTTP_201_CREATED)
def create_application(
    data: ApplicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    opp = db.query(Opportunity).filter(Opportunity.id == data.opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

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


# POST /applications/{id}/apply — Bouton Postuler intelligent

@router.post("/{application_id}/apply", response_model=ApplyResponse)
def smart_apply(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Bouton Postuler intelligent.
    1. Detecte comment postuler (lien externe, email, direct)
    2. Verifie si le dossier est pret
    3. Marque la candidature comme soumise
    4. Retourne les infos pour que le frontend agisse
    """
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

    opp = app.opportunity
    method_info = detect_application_method(opp)
    readiness = check_user_readiness(current_user, opp, db)

    # Marquer comme soumise
    app.status = "submitted"
    app.applied_at = datetime.utcnow()
    db.commit()

    method = method_info["method"]

    if method == "email":
        message = f"Ouvre ton client email et envoie ton dossier a {method_info.get('contact_email')}"
    elif readiness["ready"]:
        message = "Dossier complet ! Clique sur le lien pour finaliser ta candidature."
    else:
        missing = ", ".join(readiness["missing_docs"])
        message = f"Il te manque encore : {missing}. Tu peux quand meme acceder au formulaire."

    return ApplyResponse(
        application_id=app.id,
        method=method,
        action_url=method_info.get("action_url"),
        message=message,
        ready=readiness["ready"],
    )


# GET /applications/{id}/how-to-apply — Instructions detaillees

@router.get("/{application_id}/how-to-apply")
def how_to_apply(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retourne des instructions detaillees pour postuler :
    - Methode de candidature detectee
    - Documents a joindre
    - Email de contact si applicable
    - Lien direct
    """
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

    opp = app.opportunity
    method_info = detect_application_method(opp)
    readiness = check_user_readiness(current_user, opp, db)

    steps = []
    if method_info["method"] == "email":
        steps = [
            "Prepare tous tes documents en PDF",
            f"Envoie un email a {method_info.get('contact_email', 'ladresse indiquee')}",
            "Objet : Candidature — [Ton nom] — [Titre opportunite]",
            "Joins tous les documents requis en pieces jointes",
        ]
    else:
        steps = [
            "Clique sur le lien officiel ci-dessous",
            "Cree un compte sur la plateforme si necessaire",
            "Remplis le formulaire en ligne",
            "Uploade tes documents depuis ton coffre-fort",
            "Soumets avant la deadline",
        ]

    return {
        "method": method_info["method"],
        "action_url": method_info.get("action_url"),
        "contact_email": method_info.get("contact_email"),
        "steps": steps,
        "readiness": readiness,
        "source_url": opp.source_url,
        "deadline": str(opp.deadline) if opp.deadline else None,
    }


# PUT /applications/{id}

@router.put("/{application_id}", response_model=ApplicationWithOpportunity)
def update_application(
    application_id: uuid.UUID,
    data: ApplicationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
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


# DELETE /applications/{id}

@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    app = db.query(Application).filter(
        Application.id == application_id,
        Application.user_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(app)
    db.commit()
