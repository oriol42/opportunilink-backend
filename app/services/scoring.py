# app/services/scoring.py
# Preparation score — shown to the student on the opportunity detail page.
# Different from the relevance score: this guides the student, not the feed ranking.

from sqlalchemy.orm import Session
from app.models.user import User
from app.models.opportunity import Opportunity
from app.models.document import Document


def has_document(db: Session, user_id, doc_type: str) -> bool:
    """Checks if the user has a valid document of the given type."""
    doc = db.query(Document).filter(
        Document.user_id == user_id,
        Document.type == doc_type,
        Document.is_valid == True,
    ).first()
    return doc is not None


def compute_preparation_score(
    user: User,
    opp: Opportunity,
    db: Session,
) -> dict:
    """
    Returns a detailed preparation report for a (user, opportunity) pair.

    Each check has:
        - label: Human-readable name
        - ok: True if the criterion is met
        - fix: What to do if not ok

    The score = (ok_count / total_checks) * 100

    This is NOT used for feed ranking — it's shown on the opportunity detail page
    to help the student understand what they need to do to apply.
    """

    checks = []

    # --- Academic criteria ---

    checks.append({
        "label": "Niveau d'études",
        "ok": (
            not opp.required_level
            or user.level in opp.required_level
        ),
        "fix": f"Opportunité réservée aux niveaux : {', '.join(opp.required_level or [])}",
        "category": "academic",
    })

    if opp.min_gpa:
        checks.append({
            "label": "Moyenne suffisante",
            "ok": bool(user.gpa and user.gpa >= opp.min_gpa),
            "fix": f"Moyenne requise : {opp.min_gpa}/20 — ta moyenne : {user.gpa or 'non renseignée'}/20",
            "category": "academic",
        })

    if opp.required_languages:
        user_langs = set(user.languages or [])
        missing_langs = set(opp.required_languages) - user_langs
        checks.append({
            "label": "Langues requises",
            "ok": len(missing_langs) == 0,
            "fix": f"Langues manquantes : {', '.join(missing_langs)}",
            "category": "academic",
        })

    if opp.required_fields:
        checks.append({
            "label": "Filière compatible",
            "ok": user.field in opp.required_fields,
            "fix": f"Filières acceptées : {', '.join(opp.required_fields)}",
            "category": "academic",
        })

    # --- Documents ---

    checks.append({
        "label": "CV disponible",
        "ok": has_document(db, user.id, "cv"),
        "fix": "Uploade ton CV dans le coffre-fort documents",
        "category": "document",
    })

    checks.append({
        "label": "Relevés de notes",
        "ok": has_document(db, user.id, "releve"),
        "fix": "Uploade tes relevés de notes dans le coffre-fort",
        "category": "document",
    })

    checks.append({
        "label": "CNI ou passeport",
        "ok": has_document(db, user.id, "cni"),
        "fix": "Uploade ta CNI dans le coffre-fort",
        "category": "document",
    })

    # --- Profile completeness ---

    checks.append({
        "label": "Profil complété",
        "ok": bool(user.level and user.field and user.gpa and user.city),
        "fix": "Complete ton profil : niveau, filière, moyenne, ville",
        "category": "profile",
    })

    # --- Score calculation ---

    ok_count = sum(1 for c in checks if c["ok"])
    total = len(checks)
    score = round((ok_count / total) * 100)

    missing = [c for c in checks if not c["ok"]]

    # Build human-readable message
    if score == 100:
        message = "🎉 Ton dossier est complet ! Tu peux candidater."
    elif score >= 70:
        missing_labels = ", ".join(m["label"] for m in missing[:2])
        message = f"✅ Tu es prêt à {score}%. Il te manque : {missing_labels}"
    else:
        missing_labels = ", ".join(m["label"] for m in missing[:3])
        message = f"⚠️ Tu es prêt à {score}%. Priorité : {missing_labels}"

    return {
        "score": score,
        "checks": checks,
        "missing": missing,
        "message": message,
        "ok_count": ok_count,
        "total_checks": total,
    }
