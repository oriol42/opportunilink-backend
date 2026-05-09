import httpx
from groq import Groq
from app.config import settings
from app.models.user import User
from app.models.opportunity import Opportunity

GROQ_MODEL = "llama-3.3-70b-versatile"

LANGUAGE_NAMES = {
    "fr": "francais", "en": "anglais", "de": "allemand",
    "es": "espagnol", "zh": "chinois", "ar": "arabe", "pt": "portugais",
}

OPPORTUNITY_TYPE_NAMES = {
    "bourse": "bourse d etudes", "stage": "stage", "emploi": "emploi",
    "echange": "programme d echange", "concours": "concours",
}


def _get_client():
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not configured.")
    http_client = httpx.Client(
        transport=httpx.HTTPTransport(local_address="0.0.0.0")
    )
    return Groq(api_key=settings.groq_api_key, http_client=http_client)


def _build_letter_prompt(user, opp):
    user_level = user.level or "non precise"
    user_field = user.field or "non precise"
    user_city = user.city or "Yaounde"
    user_gpa = (str(user.gpa) + "/20") if user.gpa else "non precisee"
    user_skills = ", ".join(user.skills) if user.skills else "non precisees"
    user_languages = ", ".join(
        LANGUAGE_NAMES.get(lang, lang) for lang in (user.languages or [])
    ) or "non precisees"
    opp_type = OPPORTUNITY_TYPE_NAMES.get(opp.type, opp.type)
    opp_country = opp.country or "non precise"
    opp_levels = ", ".join(opp.required_level) if opp.required_level else "tous niveaux"
    opp_fields = ", ".join(opp.required_fields) if opp.required_fields else "toutes filieres"
    opp_deadline = str(opp.deadline) if opp.deadline else "non precisee"

    return (
        "Tu es un expert en redaction de lettres de motivation pour etudiants africains.\n\n"
        "Redige une lettre de motivation professionnelle pour ce candidat.\n\n"
        "=== PROFIL ===\n"
        f"Nom : {user.full_name}\n"
        f"Niveau : {user_level}\n"
        f"Filiere : {user_field}\n"
        f"Ville : {user_city}, Cameroun\n"
        f"Moyenne : {user_gpa}\n"
        f"Competences : {user_skills}\n"
        f"Langues : {user_languages}\n\n"
        "=== OPPORTUNITE ===\n"
        f"Titre : {opp.title}\n"
        f"Type : {opp_type}\n"
        f"Pays : {opp_country}\n"
        f"Niveaux : {opp_levels}\n"
        f"Filieres : {opp_fields}\n"
        f"Deadline : {opp_deadline}\n"
        f"Description : {opp.description[:600]}\n\n"
        "=== INSTRUCTIONS ===\n"
        "1. 4 a 5 paragraphes, 350-500 mots.\n"
        "2. Structure : accroche -> profil -> motivation -> valeur -> conclusion.\n"
        "3. Personnalise avec le profil. Mentionne le titre et le pays.\n"
        "4. Ton professionnel mais humain. En francais.\n"
        "5. Commence par Madame, Monsieur, sans en-tete.\n"
        "6. Reponds UNIQUEMENT avec le texte de la lettre."
    )


def _build_cv_prompt(user, opp):
    user_skills = ", ".join(user.skills) if user.skills else "non precisees"
    user_languages = ", ".join(
        LANGUAGE_NAMES.get(lang, lang) for lang in (user.languages or [])
    ) or "non precisees"
    opp_type = OPPORTUNITY_TYPE_NAMES.get(opp.type, opp.type)

    return (
        "Tu es un expert RH et coach de carriere specialise pour les etudiants africains.\n\n"
        "Genere des conseils d optimisation de CV pour ce candidat visant cette opportunite specifique.\n\n"
        "=== PROFIL ===\n"
        f"Nom : {user.full_name}\n"
        f"Niveau : {user.level or 'non precise'}\n"
        f"Filiere : {user.field or 'non precise'}\n"
        f"Ville : {user.city or 'Cameroun'}\n"
        f"Moyenne : {str(user.gpa) + '/20' if user.gpa else 'non precisee'}\n"
        f"Competences : {user_skills}\n"
        f"Langues : {user_languages}\n\n"
        "=== OPPORTUNITE ===\n"
        f"Titre : {opp.title}\n"
        f"Type : {opp_type}\n"
        f"Pays : {opp.country or 'non precise'}\n"
        f"Description : {(opp.description or '')[:500]}\n\n"
        "=== INSTRUCTIONS ===\n"
        "Reponds en JSON valide UNIQUEMENT, sans backticks ni texte autour.\n"
        "Format exact :\n"
        '{\n'
        '  "titre_cv": "Titre professionnel suggere pour le CV",\n'
        '  "resume": "Accroche de 2-3 phrases percutantes pour le CV",\n'
        '  "competences_a_mettre_en_avant": ["competence1", "competence2", "..."],\n'
        '  "points_a_valoriser": ["point1", "point2", "..."],\n'
        '  "conseils": ["conseil1", "conseil2", "conseil3"]\n'
        '}'
    )


def generate_motivation_letter(user: User, opp: Opportunity) -> str:
    client = _get_client()
    prompt = _build_letter_prompt(user, opp)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "Tu es un expert en redaction de lettres de motivation. Tu reponds UNIQUEMENT avec le texte de la lettre, sans commentaire."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=1024,
    )
    return completion.choices[0].message.content.strip()


def generate_cv_advice(user: User, opp: Opportunity) -> dict:
    """
    Returns a structured dict with CV optimization advice.
    Uses JSON mode via prompt instruction.
    """
    import json
    client = _get_client()
    prompt = _build_cv_prompt(user, opp)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "Tu es un expert RH. Reponds UNIQUEMENT en JSON valide, sans backticks ni texte supplementaire."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        max_tokens=800,
    )
    raw = completion.choices[0].message.content.strip()
    # Strip markdown code fences if model adds them anyway
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)
