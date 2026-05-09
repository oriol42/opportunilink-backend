from datetime import date
from sqlalchemy.orm import Session
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
    return max(0.0, score)


def extract_keywords(text: str) -> set[str]:
    if not text:
        return set()
    import re
    return set(re.findall(r'\b[a-zA-ZÀ-ÿ]{3,}\b', text.lower()))


def compute_profile_match_score(user: User, opp: Opportunity) -> float:
    score = 0.0
    if user.skills and opp.description:
        user_skills = set(s.lower() for s in user.skills)
        matches = len(user_skills.intersection(extract_keywords(opp.description)))
        score += min(matches * 10, 40)
    if user.field and opp.description:
        if user.field.lower() in opp.description.lower():
            score += 30
    if user.field and opp.type:
        if user.field.lower() in {"informatique", "génie civil", "sciences"} and opp.type == "stage":
            score += 30
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


def compute_history_score(user: User, opp: Opportunity, db: Session | None = None) -> float:
    """
    Dimension historique — score basé sur le comportement réel de l'utilisateur.
    
    Sources de signal :
    - A-t-il sauvegardé des opportunités du même type ?      → +15 pts
    - A-t-il candidaté à des opportunités du même type ?     → +20 pts
    - A-t-il une candidature acceptée dans ce domaine ?      → +15 pts
    - Pénalité si beaucoup de candidatures rejetées de ce type → -10 pts
    
    Sans DB (feed cache) → score neutre 50.
    """
    if db is None:
        return 50.0

    score = 50.0

    try:
        from app.models.saved import SavedOpportunity
        from app.models.application import Application

        # Types d'opportunités sauvegardées
        saved = db.query(SavedOpportunity).filter(
            SavedOpportunity.user_id == user.id
        ).all()
        saved_opp_ids = [s.opportunity_id for s in saved]

        if saved_opp_ids:
            saved_types = db.query(Opportunity.type).filter(
                Opportunity.id.in_(saved_opp_ids)
            ).all()
            saved_type_list = [t[0] for t in saved_types]
            if opp.type in saved_type_list:
                score += 15  # L'utilisateur aime ce type d'opportunité

        # Types d'opportunités candidatées
        apps = db.query(Application).filter(
            Application.user_id == user.id
        ).all()

        if apps:
            app_opp_ids = [a.opportunity_id for a in apps]
            app_types_query = db.query(Opportunity.type).filter(
                Opportunity.id.in_(app_opp_ids)
            ).all()
            app_type_list = [t[0] for t in app_types_query]

            if opp.type in app_type_list:
                score += 20  # A déjà candidaté à ce type

            # Bonus si accepté dans ce type
            accepted_ids = [a.opportunity_id for a in apps if a.status == "accepted"]
            if accepted_ids:
                accepted_types = db.query(Opportunity.type).filter(
                    Opportunity.id.in_(accepted_ids)
                ).all()
                if opp.type in [t[0] for t in accepted_types]:
                    score += 15  # Déjà eu du succès ici !

            # Pénalité légère si beaucoup de rejets
            rejected = [a for a in apps if a.status == "rejected"]
            if len(rejected) > 3:
                score -= 10

    except Exception:
        return 50.0

    return max(0.0, min(100.0, score))


def compute_relevance_score(user: User, opp: Opportunity, db: Session | None = None) -> float:
    e = compute_eligibility_score(user, opp)
    p = compute_profile_match_score(user, opp)
    u = compute_urgency_score(opp)
    r = compute_reliability_score(opp)
    h = compute_history_score(user, opp, db)
    return round((e * 0.40) + (p * 0.25) + (u * 0.15) + (r * 0.10) + (h * 0.10), 2)


def build_personalized_feed(
    user: User,
    opportunities: list[Opportunity],
    page: int = 1,
    limit: int = 20,
    min_score: float = 10.0,
    db: Session | None = None,
) -> list[tuple[Opportunity, float]]:
    scored = []
    for opp in opportunities:
        if opp.deadline and (opp.deadline - date.today()).days < 0:
            continue
        score = compute_relevance_score(user, opp, db)
        if score >= min_score:
            scored.append((opp, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    start = (page - 1) * limit
    return scored[start:start + limit]
