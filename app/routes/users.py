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
