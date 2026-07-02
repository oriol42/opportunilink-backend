import httpx
import json
from groq import Groq
from app.config import settings
from app.models.user import User
from app.models.opportunity import Opportunity

GROQ_MODEL = "llama-3.3-70b-versatile"

LANGUAGE_NAMES = {
    "fr": "français", "en": "anglais", "de": "allemand",
    "es": "espagnol", "zh": "chinois", "ar": "arabe", "pt": "portugais",
}

OPPORTUNITY_TYPE_NAMES = {
    "bourse": "bourse d'études", "stage": "stage", "emploi": "emploi",
    "echange": "programme d'échange", "concours": "concours",
}


def _get_client():
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not configuré.")
    return Groq(
        api_key=settings.groq_api_key,
        http_client=httpx.Client(transport=httpx.HTTPTransport(local_address="0.0.0.0")),
    )


# ── PROMPTS LETTRE & CV (inchangés, ils fonctionnaient bien) ──────────────

def _build_letter_prompt(user, opp):
    user_skills = ", ".join(user.skills) if user.skills else "non précisées"
    user_languages = ", ".join(LANGUAGE_NAMES.get(l, l) for l in (user.languages or [])) or "non précisées"
    opp_type = OPPORTUNITY_TYPE_NAMES.get(opp.type, opp.type)

    return (
        "Tu es un expert en rédaction de lettres de motivation pour étudiants africains.\n\n"
        "Rédige une lettre de motivation professionnelle pour ce candidat.\n\n"
        "=== PROFIL ===\n"
        f"Nom : {user.full_name}\n"
        f"Niveau : {user.level or 'non précisé'}\n"
        f"Filière : {user.field or 'non précisée'}\n"
        f"Ville : {user.city or 'Yaoundé'}, Cameroun\n"
        f"Moyenne : {str(user.gpa) + '/20' if user.gpa else 'non précisée'}\n"
        f"Compétences : {user_skills}\n"
        f"Langues : {user_languages}\n\n"
        "=== OPPORTUNITÉ ===\n"
        f"Titre : {opp.title}\n"
        f"Type : {opp_type}\n"
        f"Pays : {opp.country or 'non précisé'}\n"
        f"Niveaux acceptés : {', '.join(opp.required_level) if opp.required_level else 'tous'}\n"
        f"Filières acceptées : {', '.join(opp.required_fields) if opp.required_fields else 'toutes'}\n"
        f"Deadline : {str(opp.deadline) if opp.deadline else 'non précisée'}\n"
        f"Description : {(opp.description or '')[:600]}\n\n"
        "=== INSTRUCTIONS ===\n"
        "1. 4 à 5 paragraphes, 350-500 mots.\n"
        "2. Structure : accroche → profil → motivation → valeur ajoutée → conclusion.\n"
        "3. Personnalise avec le profil. Mentionne le titre et le pays.\n"
        "4. Ton professionnel mais humain. En français.\n"
        "5. Commence par 'Madame, Monsieur,' sans en-tête.\n"
        "6. Réponds UNIQUEMENT avec le texte de la lettre."
    )


def _build_cv_prompt(user, opp):
    user_skills = ", ".join(user.skills) if user.skills else "non précisées"
    user_languages = ", ".join(LANGUAGE_NAMES.get(l, l) for l in (user.languages or [])) or "non précisées"
    age_line = f"Age : {user.age} ans\n" if user.age else ""

    return (
        "Tu es un expert RH spécialisé pour les étudiants africains. "
        "Génère un CV COMPLET et prêt à l'emploi (pas des conseils, un vrai contenu de CV), "
        "optimisé pour l'opportunité ciblée, en français, avec un ton professionnel et concret.\n\n"
        "=== PROFIL ===\n"
        f"Nom : {user.full_name}\n"
        f"Niveau : {user.level or 'non précisé'}\n"
        f"Filière : {user.field or 'non précisée'}\n"
        f"Ville : {user.city or 'Cameroun'}\n"
        f"{age_line}"
        f"Moyenne : {str(user.gpa) + '/20' if user.gpa else 'non précisée'}\n"
        f"Compétences : {user_skills}\n"
        f"Langues : {user_languages}\n\n"
        "=== OPPORTUNITÉ CIBLÉE ===\n"
        f"Titre : {opp.title}\n"
        f"Type : {OPPORTUNITY_TYPE_NAMES.get(opp.type, opp.type)}\n"
        f"Pays : {opp.country or 'non précisé'}\n"
        f"Description : {(opp.description or '')[:500]}\n\n"
        "Réponds en JSON valide UNIQUEMENT, sans backticks, avec EXACTEMENT cette structure :\n"
        '{"titre_accroche":"titre professionnel court, ex: Étudiant en Informatique | Développeur Full-Stack",'
        '"resume_profil":"3-4 phrases percutantes qui résument le profil pour CETTE opportunité",'
        '"formation":[{"periode":"annee-annee ou en cours","titre":"intitule du diplome","etablissement":"nom réaliste ou generique si inconnu"}],'
        '"competences_techniques":["liste de 5-8 competences techniques, reformulees professionnellement"],'
        '"competences_transverses":["liste de 3-5 soft skills pertinents pour cette opportunite"],'
        '"langues":[{"langue":"nom","niveau":"Natif/Courant/Intermediaire/Notions"}],'
        '"points_forts":["3 phrases courtes qui valorisent le profil specifiquement pour cette opportunite"],'
        '"conseils_amelioration":["2-3 conseils concrets pour renforcer le dossier avant de postuler"]}'
    )


# ── SYSTEM PROMPT DU COACH — avec données réelles ─────────────────────────

def _build_coach_system_prompt(user: User, opportunities: list = None, context_data: dict = None) -> str:
    """
    System prompt riche : profil + opportunités réelles du feed + documents manquants + candidatures.
    Plus le contexte est riche, plus l'IA est pertinente.
    """
    from datetime import date

    user_skills = ", ".join(user.skills) if user.skills else "aucune renseignée"
    user_languages = ", ".join(LANGUAGE_NAMES.get(l, l) for l in (user.languages or [])) or "aucune renseignée"

    # Section profil
    profil_section = (
        f"Nom : {user.full_name}\n"
        f"Niveau d'études : {user.level or 'non renseigné'}\n"
        f"Filière : {user.field or 'non renseignée'}\n"
        f"Ville : {user.city or 'Cameroun'}\n"
        f"Moyenne académique : {str(user.gpa) + '/20' if user.gpa else 'non renseignée'}\n"
        f"Compétences : {user_skills}\n"
        f"Langues parlées : {user_languages}\n"
        f"Score OpportuLink : {user.opportuni_score or 0}/1000\n"
    )

    # Section opportunités du feed (les meilleures)
    opps_section = ""
    if opportunities:
        today = date.today()
        opps_lines = []
        for o in opportunities[:15]:  # max 15 pour rester dans les tokens
            days_left = None
            if o.deadline:
                days_left = (o.deadline - today).days
            deadline_str = f"J-{days_left}" if days_left is not None and days_left >= 0 else ("expirée" if days_left is not None else "non précisée")
            score = round(getattr(o, "relevance_score", 0) or 0)
            opps_lines.append(
                f"  • [{o.type.upper()}] {o.title} | {o.country or 'International'} | "
                f"Deadline: {deadline_str} | Match: {score}% | ID: {o.id}"
            )
        opps_section = "\n=== OPPORTUNITÉS DANS LE FEED DE L'ÉTUDIANT ===\n" + "\n".join(opps_lines)

    # Section contexte supplémentaire (docs manquants, candidatures)
    context_section = ""
    if context_data:
        missing_docs = context_data.get("missing_docs", [])
        applications_count = context_data.get("applications_count", 0)
        profile_pct = context_data.get("profile_pct", 0)
        if missing_docs:
            context_section += f"\nDocuments manquants dans le coffre-fort : {', '.join(missing_docs)}"
        context_section += f"\nNombre de candidatures soumises : {applications_count}"
        context_section += f"\nProfil complété à : {profile_pct}%"
        if profile_pct < 60:
            context_section += " ⚠️ (profil incomplet — recommande de le compléter)"

    return (
        "Tu es le Coach IA d'OpportuLink, expert en développement de carrière pour étudiants camerounais et africains.\n\n"
        "Tu maîtrises :\n"
        "- Les bourses internationales : DAAD, Erasmus+, Campus France, AUF, MasterCard Foundation, "
        "Bourse Excellence Éiffel, Commonwealth, Fulbright, Orange Bourses\n"
        "- Les organismes au Cameroun : MINESUP, universités publiques, entreprises locales (MTN, Orange, Dangote, Total)\n"
        "- Les organismes internationaux : ONU, UNICEF, Banque Mondiale, BAD\n"
        "- La rédaction de lettres de motivation compétitives et CV optimisés\n"
        "- Les procédures visa Schengen, visa étudiant France/Allemagne/Canada\n"
        "- La préparation aux entretiens de sélection\n\n"
        f"=== PROFIL DE L'ÉTUDIANT ===\n{profil_section}"
        f"{opps_section}"
        f"{context_section}\n\n"
        "=== TES RÈGLES ===\n"
        "1. Réponds TOUJOURS en français, avec chaleur et encouragement.\n"
        "2. Utilise le profil et les opportunités ci-dessus pour personnaliser chaque réponse.\n"
        "3. Si l'étudiant parle d'une opportunité de son feed, utilise ses vraies données (titre, deadline, pays).\n"
        "4. Sois concret : donne des étapes précises et actionnables, pas des généralités.\n"
        "5. Génère des plans d'étude structurés quand demandé (semaine par semaine si possible).\n"
        "6. Maximum 4 paragraphes OU une liste structurée — jamais les deux à la fois.\n"
        "7. Ne génère JAMAIS de fausses informations. Si tu ne sais pas, dis-le.\n"
        "8. Mentionne les documents manquants si c'est pertinent pour la question.\n"
        "9. Adapte le ton : urgence si deadline proche, encouragement si profil faible."
    )


# ── FONCTIONS PUBLIQUES ────────────────────────────────────────────────────

def generate_motivation_letter(user: User, opp: Opportunity) -> str:
    client = _get_client()
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "Tu es expert en lettres de motivation. Réponds UNIQUEMENT avec le texte de la lettre."},
            {"role": "user", "content": _build_letter_prompt(user, opp)},
        ],
        temperature=0.7,
        max_tokens=1200,
    )
    return completion.choices[0].message.content.strip()


def generate_cv_advice(user: User, opp: Opportunity) -> dict:
    client = _get_client()
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "Tu es expert RH. Réponds UNIQUEMENT en JSON valide, sans backticks."},
            {"role": "user", "content": _build_cv_prompt(user, opp)},
        ],
        temperature=0.5,
        max_tokens=1400,
    )
    raw = completion.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def chat_with_coach(
    user: User,
    message: str,
    history: list[dict],
    opportunities: list = None,
    context_data: dict = None,
) -> str:
    """
    Chat avec contexte complet : profil + opportunités réelles + docs + candidatures.
    """
    client = _get_client()
    system_prompt = _build_coach_system_prompt(user, opportunities=opportunities, context_data=context_data)

    messages = [{"role": "system", "content": system_prompt}]

    # Historique (max 12 messages = 6 échanges)
    for msg in history[-12:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": message})

    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.72,
        max_tokens=900,
    )
    return completion.choices[0].message.content.strip()
