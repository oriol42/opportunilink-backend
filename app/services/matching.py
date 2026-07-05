from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.user import User
from app.models.opportunity import Opportunity


def compute_eligibility_score(user: User, opp: Opportunity) -> float:
    score = 100.0
    if opp.required_level:
        if user.level not in opp.required_level:
            score -= 50
    if opp.required_fields:
        if user.field not in opp.required_fields:
            score -= 30
    if opp.required_languages:
        missing = set(opp.required_languages) - set(user.languages or [])
        score -= len(missing) * 20
    if opp.min_gpa and user.gpa:
        if user.gpa < opp.min_gpa:
            score -= min((opp.min_gpa - user.gpa) * 15, 40)
    if user.age is not None:
        if opp.min_age is not None and user.age < opp.min_age:
            score -= 50
        if opp.max_age is not None and user.age > opp.max_age:
            score -= 50
    return max(0.0, score)


def extract_keywords(text: str) -> set:
    if not text:
        return set()
    import re
    return set(re.findall(r'\b[a-zA-Z\xc0-\xff]{3,}\b', text.lower()))


# Mapping objectif de carrière (profil) → types d'opportunités correspondants.
# L'étudiant déclare explicitement ce qu'il cherche : c'est le signal le plus fort.
OBJECTIVE_TO_TYPES = {
    "bourse":  {"bourse"},
    "stage":   {"stage"},
    "emploi":  {"emploi"},
    "echange": {"echange"},
    "master":  {"bourse", "formation"},
    "startup": {"concours", "emploi"},
}


def compute_profile_match_score(user: User, opp: Opportunity) -> float:
    score = 0.0

    # 1. Objectif de carrière ↔ type d'opportunité (signal le plus fort)
    wanted_types = set()
    for obj in (user.objectives or []):
        wanted_types |= OBJECTIVE_TO_TYPES.get(obj, set())
    if wanted_types and opp.type in wanted_types:
        score += 35

    # 2. Filière : match officiel (required_fields) > simple mention dans la description
    if user.field:
        if opp.required_fields and user.field in opp.required_fields:
            score += 30
        elif opp.description and user.field.lower() in opp.description.lower():
            score += 15

    # 3. Compétences de l'étudiant mentionnées dans la description
    if user.skills and opp.description:
        user_skills = set(s.lower() for s in user.skills)
        matches = len(user_skills.intersection(extract_keywords(opp.description)))
        score += min(matches * 8, 25)

    return min(score, 100.0)


def compute_urgency_score(opp: Opportunity) -> float:
    if not opp.deadline:
        return 50.0
    days = (opp.deadline - date.today()).days
    if days < 0:   return 0.0
    if days <= 3:  return 100.0
    if days <= 7:  return 85.0
    if days <= 14: return 65.0
    if days <= 30: return 45.0
    if days <= 60: return 30.0
    return 15.0


def compute_reliability_score(opp: Opportunity) -> float:
    return float(opp.reliability_score or 50)


def load_user_history(user_id, db) -> dict:
    """
    Charge l historique utilisateur en 2 requetes SQL (au lieu de 6 par opportunite).
    Retourne un dict reutilisable pour toutes les opportunites du feed.
    """
    from app.models.saved import SavedOpportunity
    from app.models.application import Application

    # Requete 1 : types des opportunites sauvegardees
    saved_rows = db.query(Opportunity.type).join(
        SavedOpportunity, SavedOpportunity.opportunity_id == Opportunity.id
    ).filter(SavedOpportunity.user_id == user_id).all()
    saved_types = {r[0] for r in saved_rows}

    # Requete 2 : toutes les candidatures
    apps = db.query(Application.opportunity_id, Application.status).filter(
        Application.user_id == user_id
    ).all()

    app_opp_ids = [a[0] for a in apps]
    accepted_opp_ids = [a[0] for a in apps if a[1] == "accepted"]
    rejected_count = sum(1 for a in apps if a[1] == "rejected")

    # Types des candidatures (1 requete si apps existent)
    app_types: set = set()
    accepted_types: set = set()
    if app_opp_ids:
        rows = db.query(Opportunity.type, Opportunity.id).filter(
            Opportunity.id.in_(app_opp_ids)
        ).all()
        app_types = {r[0] for r in rows}
        id_to_type = {r[1]: r[0] for r in rows}
        accepted_types = {id_to_type[oid] for oid in accepted_opp_ids if oid in id_to_type}

    return {
        "saved_types": saved_types,
        "app_types": app_types,
        "accepted_types": accepted_types,
        "rejected_count": rejected_count,
    }


def compute_history_score(user: User, opp: Opportunity, history: dict | None = None) -> float:
    """
    Calcule le score historique a partir du dict pre-charge par load_user_history.
    Plus aucune requete DB ici — tout est deja en memoire.
    """
    if history is None:
        return 50.0
    score = 50.0
    if opp.type in history["saved_types"]:
        score += 15
    if opp.type in history["app_types"]:
        score += 20
    if opp.type in history["accepted_types"]:
        score += 15
    if history["rejected_count"] > 3:
        score -= 10
    return max(0.0, min(100.0, score))


def compute_relevance_score(user: User, opp: Opportunity, history: dict | None = None) -> float:
    e = compute_eligibility_score(user, opp)
    p = compute_profile_match_score(user, opp)
    u = compute_urgency_score(opp)
    r = compute_reliability_score(opp)
    h = compute_history_score(user, opp, history)
    # Pertinence (objectifs + filière + compétences) revalorisée à 0.35 pour des
    # résultats plus ciblés, l'éligibilité restant déterminante à 0.35.
    return round((e * 0.35) + (p * 0.35) + (u * 0.12) + (r * 0.08) + (h * 0.10), 2)


def pre_filter_opportunities(user: User, db) -> list:
    """
    Filtre SQL AVANT le scoring Python.
    Au lieu de scorer 500 opps, on filtre d abord en DB :
    - Seulement les opps actives
    - Deadline pas encore passee
    - Niveau compatible (si renseigne)
    Resultat : ~80% moins d opps a scorer = feed 5x plus rapide.
    """
    today = date.today()
    query = db.query(Opportunity).filter(
        Opportunity.is_active == True,
        or_(
            Opportunity.deadline == None,
            Opportunity.deadline >= today,
        )
    )
    if user.level:
        query = query.filter(
            or_(
                Opportunity.required_level == None,
                Opportunity.required_level == [],
                Opportunity.required_level.any(user.level),
            )
        )
    return query.limit(300).all()


def build_personalized_feed(
    user: User,
    opportunities: list,
    page: int = 1,
    limit: int = 20,
    min_score: float = 10.0,
    db=None,
) -> list:
    # Charge l historique une seule fois pour toutes les opportunites
    history = load_user_history(user.id, db) if db else None

    today = date.today()
    scored = []
    for opp in opportunities:
        if opp.deadline and (opp.deadline - today).days < 0:
            continue
        score = compute_relevance_score(user, opp, history)
        if score >= min_score:
            scored.append((opp, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    start = (page - 1) * limit
    return scored[start:start + limit]
