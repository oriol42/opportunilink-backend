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

# Identique a la liste FIELDS du frontend (app/onboarding/page.tsx) —
# permet a l IA de classer une opportunite sur les memes valeurs que user.field
FIELD_TAXONOMY = [
    "Informatique", "Génie Logiciel", "Réseaux & Télécoms", "Intelligence Artificielle",
    "Droit", "Sciences Politiques", "Relations Internationales",
    "Médecine", "Pharmacie", "Santé Publique",
    "Économie", "Gestion", "Finance", "Marketing", "Comptabilité",
    "Lettres & Sciences Humaines", "Langues", "Journalisme", "Communication",
    "Sciences", "Mathématiques", "Physique", "Chimie", "Biologie",
    "Ingénierie Civile", "Architecture", "Mécanique", "Électronique",
    "Agriculture", "Environnement", "Éducation", "Psychologie", "Sociologie",
    "Art & Design", "Audiovisuel", "Tourisme & Hôtellerie", "Autre",
]


def has_document(db: Session, user_id, doc_type: str) -> bool:
    doc = db.query(Document).filter(
        Document.user_id == user_id,
        Document.type == doc_type,
        Document.is_valid == True,
    ).first()
    return doc is not None


def extract_requirements_from_description(opp: Opportunity, use_backfill_key: bool = False) -> dict:
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
            "specific_documents": [],
            "key_skills": [],
            "lang_tests": [],
            "specific_criteria": [],
            "target_fields": [],  # inconnu -> on ne restreint pas
            "target_gender": "tous",
            "has_salary": False,
            "salary_text": None,
        }

    try:
        from app.config import settings
        # La classification en masse (backfill/tache nocturne) utilise une cle Groq
        # dediee si elle est configuree, pour ne jamais empieter sur le quota de
        # Link IA cote utilisateurs reels. Fallback sur la cle principale si absente.
        api_key = (
            settings.groq_api_key_backfill
            if use_backfill_key and settings.groq_api_key_backfill
            else settings.groq_api_key
        )
        if not api_key:
            raise ValueError("No Groq key")

        import httpx
        from groq import Groq

        http_client = httpx.Client(
            transport=httpx.HTTPTransport(local_address="0.0.0.0")
        )
        client = Groq(api_key=api_key, http_client=http_client)

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
  "specific_documents": ["documents cites explicitement dans le texte qui ne rentrent dans aucune categorie ci-dessus, avec leur libelle exact (ex: 'Extrait de casier judiciaire de moins de 3 mois', 'Registre de commerce ou carte de contribuable', 'Acte de naissance') — liste vide si aucun"],
  "key_skills": ["competences techniques specifiquement mentionnees"],
  "lang_tests": ["tests de langue requis ex: TOEFL, IELTS, DELF, DALF, TestDaF ou vide si aucun"],
  "specific_criteria": ["criteres specifiques importants non couverts ailleurs"],
  "target_fields": ["filieres d etudes reellement concernees par cette opportunite, choisies UNIQUEMENT parmi cette liste exacte : {", ".join(FIELD_TAXONOMY)}. Base-toi sur le METIER ou le SECTEUR reel de l opportunite, pas sur la simple presence d un mot dans le texte : par exemple un programme de collecte de donnees sur le VIH/SIDA concerne 'Santé Publique', pas 'Informatique', meme si le mot 'data' y apparait. Si l opportunite est explicitement ouverte a toutes les filieres (bourse generale, concours tout public, stage generaliste), renvoie une liste VIDE plutot que de deviner."],
  "target_gender": "'femmes' si l opportunite est explicitement reservee aux femmes/filles (ex: bourse Women in STEM, leadership feminin), 'hommes' si explicitement reservee aux hommes (rare), sinon 'tous'",
  "min_age": null,
  "max_age": null,
  "requires_recommendation": true or false,
  "requires_motivation_letter": true or false,
  "application_method": "email ou formulaire_en_ligne ou courrier ou plateforme",
  "has_salary": true or false,
  "salary_text": "le montant/la remuneration TELLE QUE MENTIONNEE dans le texte (ex: '800 EUR/mois', 'Bourse de 500000 FCFA/an', 'Salaire competitif selon experience') ou null si aucune remuneration n est mentionnee. Une bourse qui couvre juste les frais de scolarite n est PAS un salaire -- ne compte que les vraies allocations/salaires/stipends verses a la personne."
}}"""

        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            reasoning_effort="low",
            messages=[
                {"role": "system", "content": "Tu es un expert en analyse d offres de bourses et stages. Reponds uniquement en JSON valide."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=800,
        )

        raw = completion.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)

        # Validation : on ne garde que des filieres reellement dans notre taxonomie
        # (protege contre une hallucination du modele hors liste)
        result["target_fields"] = [
            f for f in result.get("target_fields", []) if f in FIELD_TAXONOMY
        ]
        result["specific_documents"] = [
            str(d) for d in result.get("specific_documents", []) if d
        ][:8]
        if result.get("target_gender") not in ("femmes", "hommes", "tous"):
            result["target_gender"] = "tous"

        logger.info(f"IA extraction OK pour {opp.id}: docs={result.get('required_docs')} fields={result.get('target_fields')}")
        return result

    except Exception as e:
        logger.warning(f"IA extraction failed pour {opp.id}: {e} — fallback defaults")
        return {
            "ai_extracted": False,
            "required_docs": ["cv", "releve"],
            "specific_documents": [],
            "target_fields": [],
            "target_gender": "tous",
            "key_skills": [],
            "lang_tests": [],
            "specific_criteria": [],
            "requires_recommendation": False,
            "requires_motivation_letter": True,
            "application_method": "formulaire_en_ligne",
            "has_salary": False,
            "salary_text": None,
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
        "fix": f"Opportunite reservee aux : {', '.join(opp.required_level or [])}",
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

    if opp.target_gender and opp.target_gender != "tous":
        checks.append({
            "label": "Genre",
            "ok": bool(user.gender) and user.gender == opp.target_gender,
            "fix": f"Opportunite reservee aux : {opp.target_gender}",
            "category": "academic",
        })

    # --- Documents vraiment requis ---
    # On fait confiance a ce que l IA (ou le fallback explicite si non-extrait) a determine.
    # On ne force plus cv/releve artificiellement : une opportunite qui ne les demande pas
    # ne doit pas les afficher comme manquants.
    required_docs = requirements.get("required_docs", [])

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

    # Documents specifiques cites dans le texte mais hors taxonomie coffre-fort
    # (ex: acte de naissance, casier judiciaire, registre de commerce...) —
    # on ne peut pas les verifier automatiquement, mais on ne les cache plus
    # dans un "Autre document" generique : chacun apparait avec son vrai libelle.
    for specific_doc in requirements.get("specific_documents", []):
        checks.append({
            "label": specific_doc,
            "ok": False,
            "fix": "Document specifique a cette opportunite — prepare-le selon l annonce officielle",
            "category": "document_specific",
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
            "specific_documents": requirements.get("specific_documents", []),
            "target_fields": requirements.get("target_fields", []),
            "key_skills": requirements.get("key_skills", []),
            "country": opp.country or "",
            "type": opp.type,
        },
        "application_method": requirements.get("application_method", "formulaire_en_ligne"),
        "requires_recommendation": requirements.get("requires_recommendation", False),
    }


def persist_ai_classification(db: Session, opp: Opportunity) -> dict:
    """
    Lance (ou reutilise) l extraction IA pour une opportunite, et persiste
    le resultat en base :
      - opp.required_docs (JSONB)  -> deja fait par extract_requirements_from_description
        via l appelant habituel (compute_preparation_score) ; ici on l ecrit nous-memes
        car cette fonction peut etre appelee AVANT toute visite utilisateur (crawl/backfill).
      - opp.required_fields (colonne reelle utilisee par le matching cote feed) :
        rempli UNIQUEMENT si vide, pour ne jamais ecraser une valeur saisie a la main
        par une organisation qui publie elle-meme son opportunite.

    Idempotent : si deja classifie (ai_extracted True en base), ne rappelle pas Groq.
    """
    result = extract_requirements_from_description(opp, use_backfill_key=True)

    # On persiste le blob complet (documents + criteres) dans required_docs
    opp.required_docs = result

    # Calcul de l'embedding semantique (titre + description) pour le matching
    # par similarite dans le feed. Ne recalcule pas si deja present.
    if opp.embedding is None:
        try:
            from app.services.embeddings import embed_passage, build_opportunity_text
            opp.embedding = embed_passage(build_opportunity_text(opp))
        except Exception as e:
            logger.warning(f"Calcul embedding echoue pour {opp.id}: {e}")

    # On ne remplit required_fields que s il est actuellement vide, pour respecter
    # une valeur deja fixee manuellement (ex: organisation ayant publie son offre).
    if not opp.required_fields:
        opp.required_fields = result.get("target_fields", [])
    if not opp.target_gender:
        opp.target_gender = result.get("target_gender", "tous")

    db.add(opp)
    db.commit()
    db.refresh(opp)
    return result
