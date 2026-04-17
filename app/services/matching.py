# app/services/matching.py
# Recommendation algorithm — scores (user, opportunity) pairs
# No ML needed: pure Python business logic is enough for the MVP.
# The 5 dimensions are weighted and combined into a final relevance score.

from datetime import date
from app.models.user import User
from app.models.opportunity import Opportunity

# DIMENSION 1 — Eligibility (40%)
# Hard filter: is the user actually eligible?


def compute_eligibility_score(user: User, opp: Opportunity) -> float:
    score = 100.0

    # Level check — most eliminatory criterion
    if opp.required_level:
        if user.level not in opp.required_level:
            score -= 50

    # Field check
    if opp.required_fields:
        if user.field not in opp.required_fields:
            score -= 30

    # Language check — penalize each missing language
    if opp.required_languages:
        user_langs = set(user.languages or [])
        missing = set(opp.required_languages) - user_langs
        score -= len(missing) * 20

    # GPA check — proportional penalty
    if opp.min_gpa and user.gpa:
        if user.gpa < opp.min_gpa:
            gap = opp.min_gpa - user.gpa
            score -= min(gap * 15, 40)

    return max(0.0, score)


# DIMENSION 2 — Profile match (25%)
# Beyond eligibility: how well does the opportunity fit?


def extract_keywords(text: str) -> set[str]:
    """
    Simple tokenizer — splits description into lowercase words.
    No NLP needed at this stage: keyword intersection is enough.
    """
    if not text:
        return set()
    # Remove punctuation, lowercase, split
    import re
    words = re.findall(r'\b[a-zA-ZÀ-ÿ]{3,}\b', text.lower())
    return set(words)


def compute_profile_match_score(user: User, opp: Opportunity) -> float:
    score = 0.0

    # Skill matching — how many user skills appear in the description
    if user.skills and opp.description:
        user_skills = set(s.lower() for s in user.skills)
        opp_keywords = extract_keywords(opp.description)
        matches = len(user_skills.intersection(opp_keywords))
        score += min(matches * 10, 40)  # Max 40 pts

    # Field in description — domain relevance
    if user.field and opp.description:
        if user.field.lower() in opp.description.lower():
            score += 30

    # Type bonus — if opportunity type matches user's field context
    # (simple heuristic: CS students benefit more from tech internships)
    if user.field and opp.type:
        tech_fields = {"informatique", "génie civil", "sciences"}
        if user.field.lower() in tech_fields and opp.type == "stage":
            score += 30

    return min(score, 100.0)



# DIMENSION 3 — Urgency (15%)
# Boost opportunities with approaching deadlines


def compute_urgency_score(opp: Opportunity) -> float:
    if not opp.deadline:
        return 50.0  # Neutral if no deadline

    days_left = (opp.deadline - date.today()).days

    if days_left < 0:
        return 0.0    # Expired — will be filtered out anyway
    elif days_left <= 3:
        return 100.0
    elif days_left <= 7:
        return 85.0
    elif days_left <= 14:
        return 65.0
    elif days_left <= 30:
        return 45.0
    elif days_left <= 60:
        return 30.0
    else:
        return 15.0


# DIMENSION 4 — Reliability (10%)
# Don't surface suspicious opportunities

def compute_reliability_score(opp: Opportunity) -> float:
    # reliability_score is already 0-100 from the anti-scam pipeline
    return float(opp.reliability_score or 50)


# DIMENSION 5 — History (10%)
# Learn from the user's past behavior
# Simplified version: no DB queries here yet (Phase 2 will add this)


def compute_history_score(user: User, opp: Opportunity) -> float:
    # Default neutral score — will be personalized in Phase 2
    # when we have enough user interaction data
    return 50.0


# FINAL SCORE — Weighted combination


def compute_relevance_score(user: User, opp: Opportunity) -> float:
    """
    Computes the final relevance score for a (user, opportunity) pair.
    Returns a float between 0 and 100.

    Weights:
        Eligibility  40% — Can the user apply at all?
        Profile      25% — Does it fit their profile?
        Urgency      15% — Is the deadline approaching?
        Reliability  10% — Is the source trustworthy?
        History      10% — Does it match past behavior?
    """
    e = compute_eligibility_score(user, opp)
    p = compute_profile_match_score(user, opp)
    u = compute_urgency_score(opp)
    r = compute_reliability_score(opp)
    h = compute_history_score(user, opp)

    final = (e * 0.40) + (p * 0.25) + (u * 0.15) + (r * 0.10) + (h * 0.10)

    return round(final, 2)



# FEED BUILDER — Scores and ranks all active opportunities

def build_personalized_feed(
    user: User,
    opportunities: list[Opportunity],
    page: int = 1,
    limit: int = 20,
    min_score: float = 10.0,
) -> list[tuple[Opportunity, float]]:
    """
    Takes a user and a list of active opportunities.
    Returns a sorted, paginated list of (opportunity, score) tuples.

    Args:
        user: The authenticated user
        opportunities: All active opportunities from DB
        page: Page number (1-indexed)
        limit: Items per page
        min_score: Minimum score to appear in feed (filters irrelevant opps)

    Returns:
        List of (Opportunity, relevance_score) sorted by score descending
    """
    scored = []

    for opp in opportunities:
        # Skip expired opportunities
        if opp.deadline and (opp.deadline - date.today()).days < 0:
            continue

        score = compute_relevance_score(user, opp)

        # Only include opportunities above the minimum threshold
        if score >= min_score:
            scored.append((opp, score))

    # Sort by score descending — best match first
    scored.sort(key=lambda x: x[1], reverse=True)

    # Pagination
    start = (page - 1) * limit
    end = start + limit

    return scored[start:end]
