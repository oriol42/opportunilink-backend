# app/routes/users.py
# User routes — profile management

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserProfileUpdate
from app.core.dependencies import get_current_user

router = APIRouter()



# GET /me — Mon profil complet

@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: User = Depends(get_current_user)):
    """
    Returns the authenticated user's full profile.

    No DB query needed here — get_current_user already fetched
    the user object from DB and passed it directly.
    """
    return current_user


# PUT /me — Mettre à jour mon profil


@router.put("/me", response_model=UserResponse)
def update_my_profile(
    updates: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Updates the authenticated user's profile.

    Only fields provided in the request body are updated.
    Fields not included stay unchanged — this is a PATCH-style update
    even though we use PUT (simpler for the frontend at this stage).

    Flow:
    1. get_current_user verifies the JWT and returns the user
    2. We iterate over the provided fields
    3. We update only the non-null fields
    4. We save and return the updated user
    """

    # model_dump(exclude_unset=True) returns ONLY the fields
    # the client actually sent — not the ones that defaulted to None
    # Example: if client sends {"city": "Yaoundé"}, we get {"city": "Yaoundé"}
    # and NOT {"full_name": None, "level": None, "city": "Yaoundé", ...}
    update_data = updates.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update",
        )

    # Apply each update to the SQLAlchemy model object
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    # Invalider le cache feed — le profil a change, les scores changent
    from app.services.cache import cache_delete_pattern
    cache_delete_pattern(f"feed:user:{current_user.id}*")

    # Recalcule l'embedding semantique en tache de fond si un champ pertinent
    # pour le matching a change. En Celery : le modele (~220MB) ne charge
    # jamais dans le process web, seulement dans le worker.
    relevant_fields = {"field", "skills", "objectives"}
    if relevant_fields.intersection(update_data.keys()):
        from app.tasks.embedding_tasks import recompute_user_embedding
        recompute_user_embedding.delay(str(current_user.id))

    return current_user


# GET /me/score — OpportuScore détaillé


@router.get("/me/score")
def get_my_score(current_user: User = Depends(get_current_user)):
    """
    Returns the user's OpportuScore with a breakdown.
    The full scoring logic will live in services/scoring.py (Phase 1).
    For now we return the raw score with basic profile completion info.
    """

    # Basic profile completion check
    profile_fields = {
        "level": current_user.level,
        "field": current_user.field,
        "city": current_user.city,
        "gpa": current_user.gpa,
        "phone": current_user.phone,
        "languages": current_user.languages,
        "skills": current_user.skills,
    }

    filled = {k: v for k, v in profile_fields.items() if v}
    missing = [k for k, v in profile_fields.items() if not v]

    completion_pct = round((len(filled) / len(profile_fields)) * 100)

    return {
        "opportuni_score": current_user.opportuni_score,
        "profile_completion": completion_pct,
        "filled_fields": list(filled.keys()),
        "missing_fields": missing,
        "message": (
            f"Profil complété à {completion_pct}%."
            if completion_pct == 100
            else f"Complète ton profil pour booster ton score. Manquant : {', '.join(missing[:3])}"
        ),
    }

# GET /users/me/stats — Statistiques personnelles complètes

@router.get("/me/stats")
def get_my_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retourne les statistiques complètes de l'utilisateur :
    candidatures par statut, favoris, documents, score profil.
    """
    from app.models.application import Application
    from app.models.document import Document
    from app.models.saved import SavedOpportunity

    apps = db.query(Application).filter(Application.user_id == current_user.id).all()
    docs = db.query(Document).filter(Document.user_id == current_user.id).all()
    saved = db.query(SavedOpportunity).filter(SavedOpportunity.user_id == current_user.id).count()

    profile_fields = [
        current_user.level, current_user.field, current_user.city,
        current_user.gpa, current_user.phone,
        current_user.languages if current_user.languages else None,
        current_user.skills if current_user.skills else None,
    ]
    profile_pct = round(sum(1 for f in profile_fields if f) / len(profile_fields) * 100)

    doc_types = {d.type for d in docs}
    essential = {"cv", "releve", "cni", "attestation"}
    doc_pct = round(len(doc_types & essential) / len(essential) * 100)

    return {
        "applications": {
            "total":     len(apps),
            "draft":     sum(1 for a in apps if a.status == "draft"),
            "submitted": sum(1 for a in apps if a.status == "submitted"),
            "accepted":  sum(1 for a in apps if a.status == "accepted"),
            "rejected":  sum(1 for a in apps if a.status == "rejected"),
        },
        "saved_count":       saved,
        "documents_count":   len(docs),
        "document_pct":      doc_pct,
        "profile_pct":       profile_pct,
        "opportuni_score":   current_user.opportuni_score,
        "member_since":      current_user.created_at.strftime("%B %Y"),
    }


# GET /users/me/coaching — Prochaine action recommandée

@router.get("/me/coaching")
def get_coaching(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyse le profil et l'activité de l'utilisateur.
    Retourne UNE prochaine action prioritaire + des insights.
    Principe : toujours donner quelque chose d'actionnable.
    """
    from app.models.application import Application
    from app.models.document import Document
    from app.models.saved import SavedOpportunity
    from app.models.opportunity import Opportunity
    from datetime import date, timedelta

    apps  = db.query(Application).filter(Application.user_id == current_user.id).all()
    docs  = db.query(Document).filter(Document.user_id == current_user.id).all()
    saved = db.query(SavedOpportunity).filter(SavedOpportunity.user_id == current_user.id).all()
    doc_types = {d.type for d in docs}

    # Deadlines urgentes dans les favoris
    urgent = []
    if saved:
        opp_ids = [s.opportunity_id for s in saved]
        opps = db.query(Opportunity).filter(
            Opportunity.id.in_(opp_ids),
            Opportunity.is_active == True,
        ).all()
        for opp in opps:
            if opp.deadline:
                days = (opp.deadline - date.today()).days
                if 0 <= days <= 7:
                    urgent.append({"title": opp.title, "days": days, "id": str(opp.id)})
        urgent.sort(key=lambda x: x["days"])

    # Déterminer la prochaine action prioritaire
    action = None
    action_type = None

    if urgent:
        # Priorité 1 — deadline urgente dans les favoris
        u = urgent[0]
        action = f"Tu as sauvegardé \"{u['title'][:50]}\" — deadline dans {u['days']} jour(s). C'est le moment de postuler."
        action_type = "urgent"
        action_url  = f"/opportunity/{u['id']}"
        action_cta  = "Postuler maintenant →"

    elif not current_user.level or not current_user.field:
        # Priorité 2 — profil incomplet bloquant
        action = "Ton niveau d'études et ta filière ne sont pas renseignés. Sans ça, le feed ne peut pas calculer ton score de pertinence."
        action_type = "profile"
        action_url  = "/dashboard/profile"
        action_cta  = "Compléter mon profil →"

    elif "cv" not in doc_types:
        # Priorité 3 — CV manquant (bloquant pour prep score)
        action = "Tu n'as pas encore uploadé ton CV. Sans lui, ton score de préparation sera faible sur toutes les opportunités."
        action_type = "document"
        action_url  = "/dashboard/documents"
        action_cta  = "Uploader mon CV →"

    elif not current_user.gpa:
        # Priorité 4 — moyenne manquante
        action = "Ta moyenne n'est pas renseignée. Elle détermine ton éligibilité à 60% des bourses disponibles."
        action_type = "profile"
        action_url  = "/dashboard/profile"
        action_cta  = "Ajouter ma moyenne →"

    elif "releve" not in doc_types:
        action = "Tes relevés de notes sont manquants. Ils sont requis par la majorité des bourses."
        action_type = "document"
        action_url  = "/dashboard/documents"
        action_cta  = "Uploader mes relevés →"

    elif not apps:
        action = "Tu n'as encore aucune candidature. Consulte le feed et postule à une opportunité qui te correspond."
        action_type = "apply"
        action_url  = "/dashboard"
        action_cta  = "Voir les opportunités →"

    elif len(apps) > 0 and all(a.status == "draft" for a in apps):
        action = f"Tu as {len(apps)} candidature(s) en brouillon. N'oublie pas de les soumettre avant les deadlines."
        action_type = "submit"
        action_url  = "/dashboard/applications"
        action_cta  = "Voir mes candidatures →"

    else:
        action = "Ton dossier est bien avancé ! Explore le feed pour trouver de nouvelles opportunités qui te correspondent."
        action_type = "explore"
        action_url  = "/dashboard"
        action_cta  = "Explorer le feed →"

    # Insights — métriques utiles
    submitted_count = sum(1 for a in apps if a.status == "submitted")
    accepted_count  = sum(1 for a in apps if a.status == "accepted")
    docs_pct = round(len(doc_types & {"cv", "releve", "cni", "attestation"}) / 4 * 100)

    profile_fields = [
        current_user.level, current_user.field, current_user.gpa,
        current_user.city, current_user.phone,
        current_user.languages if current_user.languages else None,
        current_user.skills if current_user.skills else None,
    ]
    profile_pct = round(sum(1 for f in profile_fields if f) / len(profile_fields) * 100)

    return {
        "action": action,
        "action_type": action_type,
        "action_url": action_url,
        "action_cta": action_cta,
        "urgent_deadlines": urgent[:3],
        "insights": {
            "profile_pct":    profile_pct,
            "docs_pct":       docs_pct,
            "applied":        len(apps),
            "submitted":      submitted_count,
            "accepted":       accepted_count,
            "saved":          len(saved),
            "missing_docs":   list({"cv", "releve", "cni", "attestation"} - doc_types),
        },
    }
