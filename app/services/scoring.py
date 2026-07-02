# app/services/scoring.py
# Score de preparation — montre a l etudiant ce qu il lui manque
# NOUVEAU : extraction IA des vrais documents requis depuis la description

import json
import logging
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.opportunity import Opportunity
from app.models.document import Document

logger = logging.getLogger(__name__)


def has_document(db: Session, user_id, doc_type: str) -> bool:
    doc = db.query(Document).filter(
        Document.user_id == user_id,
        Document.type == doc_type,
        Document.is_valid == True,
    ).first()
    return doc is not None


def extract_requirements_from_description(opp: Opportunity) -> dict:
    """
    Utilise Groq/Llama pour extraire depuis la description :
    - Les documents vraiment requis
    - Les competences cles demandees
    - Les tests de langue requis (TOEFL, DELF...)
    - Les criteres specifiques

    On stocke le resultat dans opp.required_docs (JSONB) pour
    ne pas rappeler l IA a chaque fois.
    """
    # Si deja extrait et stocke en DB, on reutilise
    if opp.required_docs and opp.required_docs.get("ai_extracted"):
        return opp.required_docs

    # Si pas de description, retourner des defaults
    if not opp.description or len(opp.description) < 50:
        return {
            "ai_extracted": False,
            "required_docs": ["cv", "releve"],
            "key_skills": [],
            "lang_tests": [],
            "specific_criteria": [],
        }

    try:
        from app.config import settings
        if not settings.groq_api_key:
            raise ValueError("No Groq key")

        import httpx
        from groq import Groq

        http_client = httpx.Client(
            transport=httpx.HTTPTransport(local_address="0.0.0.0")
        )
        client = Groq(api_key=settings.groq_api_key, http_client=http_client)

        prompt = f"""Analyse cette description d opportunite et extrait les informations en JSON.

DESCRIPTION :
{opp.description[:1500]}

TITRE : {opp.title}
TYPE : {opp.type}
PAYS : {opp.country or "non precise"}

Reponds UNIQUEMENT avec ce JSON valide, sans backticks :
{{
  "ai_extracted": true,
  "required_docs": ["liste des documents requis parmi : cv, releve, cni, lettre_motivation, lettre_recommandation, photo, diplome, attestation, portfolio, autre"],
  "key_skills": ["competences techniques specifiquement mentionnees"],
  "lang_tests": ["tests de langue requis ex: TOEFL, IELTS, DELF, DALF, TestDaF ou vide si aucun"],
  "specific_criteria": ["criteres specifiques importants non couverts ailleurs"],
  "min_age": null,
  "max_age": null,
  "requires_recommendation": true or false,
  "requires_motivation_letter": true or false,
  "application_method": "email ou formulaire_en_ligne ou courrier ou plateforme"
}}"""

        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Tu es un expert en analyse d offres de bourses et stages. Reponds uniquement en JSON valide."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        raw = completion.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        logger.info(f"IA extraction OK pour {opp.id}: {result.get('required_docs')}")
        return result

    except Exception as e:
        logger.warning(f"IA extraction failed pour {opp.id}: {e} — fallback defaults")
        return {
            "ai_extracted": False,
            "required_docs": ["cv", "releve"],
            "key_skills": [],
            "lang_tests": [],
            "specific_criteria": [],
            "requires_recommendation": False,
            "requires_motivation_letter": True,
            "application_method": "formulaire_en_ligne",
        }


DOC_LABELS = {
    "cv": "CV",
    "releve": "Relevés de notes",
    "cni": "CNI ou Passeport",
    "lettre_motivation": "Lettre de motivation",
    "lettre_recommandation": "Lettre de recommandation",
    "photo": "Photo d identite",
    "diplome": "Diplôme",
    "attestation": "Attestation d inscription",
    "portfolio": "Portfolio",
    "autre": "Autre document",
}

DOC_FIX = {
    "cv": "Uploade ton CV dans le coffre-fort Documents",
    "releve": "Uploade tes relevés de notes dans le coffre-fort",
    "cni": "Uploade ta CNI ou passeport dans le coffre-fort",
    "lettre_motivation": "Génère ta lettre de motivation avec le Coach IA",
    "lettre_recommandation": "Contacte un professeur ou superviseur pour une lettre",
    "photo": "Uploade une photo d identite dans le coffre-fort",
    "diplome": "Uploade une copie de ton diplôme dans le coffre-fort",
    "attestation": "Uploade une attestation d inscription de ton université",
    "portfolio": "Prépare un portfolio avec tes meilleurs travaux",
    "autre": "Vérifie les documents requis sur le site officiel",
}


def compute_preparation_score(user: User, opp: Opportunity, db: Session) -> dict:
    """
    Score de preparation INTELLIGENT :
    1. Extrait les vrais criteres depuis la description (via IA)
    2. Verifie chaque critere contre le profil et les documents
    3. Retourne un rapport detaille avec quoi faire
    """
    requirements = extract_requirements_from_description(opp)
    checks = []

    # --- Criteres academiques ---
    checks.append({
        "label": "Niveau d etudes",
        "ok": not opp.required_level or user.level in opp.required_level,
        "fix": f"Niveau requis : {', '.join(opp.required_level or [])}",
        "category": "academic",
    })

    if opp.min_gpa:
        checks.append({
            "label": "Moyenne suffisante",
            "ok": bool(user.gpa and user.gpa >= opp.min_gpa),
            "fix": f"Moyenne requise : {opp.min_gpa}/20 — ta moyenne : {user.gpa or 'non renseignee'}/20",
            "category": "academic",
        })

    if opp.min_age is not None or opp.max_age is not None:
        age_ok = user.age is not None and \
            (opp.min_age is None or user.age >= opp.min_age) and \
            (opp.max_age is None or user.age <= opp.max_age)
        borne = f"{opp.min_age or 0}-{opp.max_age or '∞'} ans"
        checks.append({
            "label": "Age requis",
            "ok": age_ok,
            "fix": f"Age requis : {borne} — renseigne ton age dans ton profil" if user.age is None
                   else f"Age requis : {borne} — ton age : {user.age} ans",
            "category": "academic",
        })

    if opp.required_languages:
        user_langs = set(user.languages or [])
        missing_langs = set(opp.required_languages) - user_langs
        lang_names = {"fr": "Français", "en": "Anglais", "de": "Allemand",
                      "es": "Espagnol", "zh": "Chinois", "ar": "Arabe"}
        missing_names = [lang_names.get(l, l) for l in missing_langs]
        checks.append({
            "label": "Langues requises",
            "ok": len(missing_langs) == 0,
            "fix": f"Langues manquantes : {', '.join(missing_names)}",
            "category": "academic",
        })

    # Tests de langue (TOEFL, DELF...)
    for test in requirements.get("lang_tests", []):
        checks.append({
            "label": f"Certificat {test}",
            "ok": False,  # On ne peut pas verifier sans que l etudiant le renseigne
            "fix": f"Ce programme demande un {test} — verifie si tu en as un",
            "category": "academic",
        })

    if opp.required_fields:
        checks.append({
            "label": "Filiere compatible",
            "ok": user.field in opp.required_fields,
            "fix": f"Filieres acceptees : {', '.join(opp.required_fields)}",
            "category": "academic",
        })

    # --- Documents vraiment requis ---
    required_docs = requirements.get("required_docs", ["cv", "releve"])

    # Toujours verifier CV et releve comme base
    if "cv" not in required_docs:
        required_docs = ["cv"] + required_docs
    if "releve" not in required_docs:
        required_docs = required_docs + ["releve"]

    for doc_type in required_docs:
        # Mapper les types IA vers les types coffre-fort
        vault_type = doc_type
        if doc_type == "lettre_motivation":
            # On ne peut pas verifier une lettre generee dans le coffre fort
            # mais on peut verifier si l etudiant a genere une lettre pour cette opp
            checks.append({
                "label": DOC_LABELS.get(doc_type, doc_type),
                "ok": False,  # On indique qu il faut en generer une
                "fix": DOC_FIX.get(doc_type, "Preparer ce document"),
                "category": "document",
            })
            continue
        if doc_type == "lettre_recommandation":
            checks.append({
                "label": DOC_LABELS.get(doc_type, doc_type),
                "ok": False,
                "fix": DOC_FIX.get(doc_type, "Preparer ce document"),
                "category": "document",
            })
            continue

        checks.append({
            "label": DOC_LABELS.get(doc_type, doc_type),
            "ok": has_document(db, user.id, vault_type),
            "fix": DOC_FIX.get(doc_type, f"Uploade ce document dans le coffre-fort"),
            "category": "document",
        })

    # --- Profil complet ---
    checks.append({
        "label": "Profil complet",
        "ok": bool(user.level and user.field and user.gpa and user.city),
        "fix": "Complete ton profil : niveau, filiere, moyenne, ville",
        "category": "profile",
    })

    # Competences cles mentionnees dans la description
    key_skills = requirements.get("key_skills", [])
    if key_skills and user.skills:
        user_skills_lower = [s.lower() for s in user.skills]
        missing_skills = [s for s in key_skills[:3] if s.lower() not in user_skills_lower]
        if missing_skills:
            checks.append({
                "label": f"Competences : {', '.join(missing_skills[:2])}",
                "ok": False,
                "fix": f"Ajoute ces competences a ton profil ou developpe-les",
                "category": "skills",
            })

    # --- Calcul score ---
    ok_count = sum(1 for c in checks if c["ok"])
    total = len(checks)
    score = round((ok_count / total) * 100) if total > 0 else 0
    missing = [c for c in checks if not c["ok"]]

    if score == 100:
        message = "Ton dossier est complet ! Tu peux candidater."
    elif score >= 70:
        missing_labels = ", ".join(m["label"] for m in missing[:2])
        message = f"Tu es pret a {score}%. Il te manque : {missing_labels}"
    else:
        missing_labels = ", ".join(m["label"] for m in missing[:3])
        message = f"Priorite : {missing_labels}"

    return {
        "score": score,
        "checks": checks,
        "missing": missing,
        "message": message,
        "ok_count": ok_count,
        "total_checks": total,
        "requirements": {
            "required_levels": opp.required_level or [],
            "required_languages": opp.required_languages or [],
            "lang_tests": requirements.get("lang_tests", []),
            "min_gpa": opp.min_gpa,
            "required_docs": requirements.get("required_docs", []),
            "key_skills": requirements.get("key_skills", []),
            "country": opp.country or "",
            "type": opp.type,
        },
        "application_method": requirements.get("application_method", "formulaire_en_ligne"),
        "requires_recommendation": requirements.get("requires_recommendation", False),
    }
