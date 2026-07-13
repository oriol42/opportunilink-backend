import httpx
import json
from groq import Groq
from app.config import settings
from app.models.user import User
from app.models.opportunity import Opportunity

GROQ_MODEL = "openai/gpt-oss-120b"

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


# ── RECHERCHE WEB — via groq/compound ───────────────────────────────────────
# Groq propose un modèle spécial qui fait lui-même la recherche web côté
# serveur (pas besoin de gérer un tool-calling maison, ni de clé Tavily).
# On détecte juste si la question a besoin d'infos fraîches, et si oui on
# route vers ce modèle pour CET échange uniquement (le reste du chat continue
# sur openai/gpt-oss-120b, le remplaçant recommandé par Groq).
COMPOUND_MODEL = "groq/compound"

_FRESH_INFO_KEYWORDS = (
    "quand", "date limite", "deadline", "ouvre", "ouverture", "cette annee",
    "en 2026", "en 2027", "recent", "recemment", "actualite", "aujourd'hui",
    "dernier", "derniere", "nouveau critere", "nouvelle regle", "a jour",
    "when", "latest", "this year", "currently", "open now",
)


def _strip_accents(s: str) -> str:
    import unicodedata
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _needs_fresh_info(message: str) -> bool:
    # On enleve les accents avant de comparer : les etudiants tapent vite et
    # sans accents ("cette anne", "derniere") -- sans ca, le mot-cle ne
    # matchait jamais et la question ne declenchait pas la recherche web.
    m = _strip_accents(message.lower())
    return any(kw in m for kw in _FRESH_INFO_KEYWORDS)


def extract_pdf_text(file_bytes: bytes) -> str:
    """Extrait le texte d'un PDF (retourne '' si scan/image sans texte)."""
    import io
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception:
        return ""


def analyze_document_text(text: str, doc_type: str) -> dict:
    """
    Analyse le texte d'un document (CV, relevé…) via Groq et extrait des infos
    structurées pour enrichir le profil de l'étudiant.
    """
    client = _get_client()
    prompt = (
        f"Analyse ce document (type : {doc_type}) d'un étudiant africain et extrais les informations "
        "utiles pour enrichir son profil.\n"
        "Réponds UNIQUEMENT en JSON valide (sans backticks) avec EXACTEMENT ces clés :\n"
        '{"skills": ["compétences techniques concrètes détectées, max 12"], '
        '"field": "filière/domaine principal ou null", '
        '"level": "niveau d\'études (Licence/Master/Doctorat/BTS/DUT/Ingénieur) ou null", '
        '"gpa": moyenne_sur_20_en_nombre_ou_null, '
        '"summary": "résumé du profil en une phrase"}\n\n'
        "=== DOCUMENT ===\n" + text[:4000]
    )
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "Tu es un assistant RH. Réponds uniquement en JSON valide, sans backticks ni texte autour."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=700,
    )
    raw = completion.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def translate_text(text: str, target_lang: str = "fr") -> str:
    """
    Traduit un texte vers la langue cible (fr, en, ...) via Groq.
    Conserve la mise en forme (paragraphes) et renvoie uniquement la traduction.
    """
    if not text or not text.strip():
        return text
    client = _get_client()
    lang_name = LANGUAGE_NAMES.get(target_lang, target_lang)
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": (
                f"Tu es un traducteur professionnel. Traduis fidèlement le texte en {lang_name}. "
                "Conserve le sens, le ton et la mise en forme (paragraphes, listes, sauts de ligne). "
                "Réponds UNIQUEMENT avec la traduction, sans introduction, note ni commentaire."
            )},
            {"role": "user", "content": text[:4000]},
        ],
        temperature=0.2,
    )
    return completion.choices[0].message.content.strip()


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

def _build_coach_system_prompt(user: User, opportunities: list = None, context_data: dict = None, focus_opp: Opportunity = None) -> str:
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

    # Section "opportunité en focus" — chat contextuel ouvert depuis une page opportunité
    focus_section = ""
    if focus_opp is not None:
        fo_deadline = str(focus_opp.deadline) if focus_opp.deadline else "non précisée"
        focus_section = (
            "\n\n=== OPPORTUNITÉ ACTUELLEMENT CONSULTÉE (l'étudiant veut en parler) ===\n"
            f"Titre : {focus_opp.title}\n"
            f"Type : {focus_opp.type}\n"
            f"Pays : {focus_opp.country or 'non précisé'}\n"
            f"Deadline : {fo_deadline}\n"
            f"Niveaux acceptés : {', '.join(focus_opp.required_level) if focus_opp.required_level else 'tous'}\n"
            f"Filières acceptées : {', '.join(focus_opp.required_fields) if focus_opp.required_fields else 'toutes'}\n"
            f"Description : {(focus_opp.description or '')[:800]}\n"
            "→ Aide l'étudiant à évaluer si cette opportunité lui correspond et à préparer sa candidature."
        )

    return (
        "Tu es **Link IA**, le coach carrière d'OpportuniLink. Tu parles comme un pote plus âgé qui "
        "s'y connaît vraiment en bourses/stages/emplois pour étudiants camerounais et africains — "
        "pas comme un chatbot de service client. Direct, chaleureux, jamais mielleux ni scolaire.\n\n"
        "Tu maîtrises :\n"
        "- Les bourses internationales : DAAD, Erasmus+, Campus France, AUF, MasterCard Foundation, "
        "Bourse Excellence Éiffel, Commonwealth, Fulbright, Orange Bourses\n"
        "- Les organismes au Cameroun : MINESUP, universités publiques, entreprises locales (MTN, Orange, Dangote, Total)\n"
        "- Les organismes internationaux : ONU, UNICEF, Banque Mondiale, BAD\n"
        "- La rédaction de lettres de motivation compétitives et CV optimisés\n"
        "- Les procédures visa Schengen, visa étudiant France/Allemagne/Canada\n"
        "- La préparation aux entretiens de sélection\n\n"
        f"=== PROFIL DE L'ÉTUDIANT (à ta disposition, PAS à réciter) ===\n{profil_section}"
        f"{opps_section}"
        f"{context_section}"
        f"{focus_section}\n\n"
        "=== COMMENT TU PARLES ===\n"
        "1. Français, ton direct et humain — jamais de formules toutes faites comme « Comment "
        "puis-je t'aider aujourd'hui ? » ou « N'hésite pas à me poser tes questions ».\n"
        "2. MIROIR DE TON : si l'étudiant écrit en style texto/décontracté (« yo », « slt », fautes, "
        "pas de majuscules), tu réponds pareil — court, familier, sans devenir un rapport d'analyse. "
        "« yo » appelle « Hey ! Ça va ? Tu cherches quoi aujourd'hui ? » — PAS un topo sur son profil.\n"
        "3. NE PARLE JAMAIS du pourcentage de complétion du profil, des documents manquants ou du nombre "
        "de candidatures SAUF SI l'étudiant pose une question qui s'y rapporte directement (son dossier, "
        "sa préparation, son profil). Ces infos sont pour TOI, pas un sujet de conversation par défaut.\n"
        "4. LONGUEUR = celle d'un vrai message, pas d'un rapport. Message court/casual → 1-2 phrases MAX. "
        "Question précise → réponse ciblée, sans plan en 5 points si pas demandé. Réserve les listes/structures "
        "aux cas où l'étudiant demande vraiment un plan, une comparaison ou une checklist.\n"
        "5. Termine par une relance SEULEMENT quand elle est naturelle et utile — pas systématiquement. "
        "Beaucoup de messages n'ont pas besoin de question de suivi.\n"
        "6. Personnalise avec les VRAIES opportunités du feed ci-dessus (titre, deadline, pays réels) quand pertinent, "
        "sans les plaquer artificiellement dans une réponse qui n'en a pas besoin.\n"
        "7. PLANS DE PRÉPARATION — avant d'en générer un : si tu ne sais pas combien de temps par semaine l'étudiant "
        "peut y consacrer ni son niveau actuel sur les compétences requises, DEMANDE-LE d'abord au lieu de sortir "
        "un plan générique « semaine 1 : ceci, semaine 2 : cela ». Une fois que tu as ces infos (ou si l'étudiant "
        "les a données), construis un plan qui tient compte : du temps réel qu'il a jusqu'à la deadline, de ce qu'il "
        "maîtrise déjà (pas besoin de bosser une compétence qu'il a), et de ce qui lui manque vraiment d'après son profil "
        "et le score de préparation. Le plan doit ressembler à un vrai conseil personnalisé, pas un template recopié.\n"
        "8. Infos datées/récentes (ouverture d'une bourse, deadline précise, nouveau critère) : base-toi sur les infos "
        "les plus à jour dont tu disposes, cite la source, et rappelle de vérifier l'officiel. N'invente jamais une date : "
        "si tu ne sais pas, dis-le simplement, sans blabla d'excuse.\n"
        "9. Adapte le ton au contexte : urgence sobre si deadline proche, encouragement sincère si le profil est faible "
        "— jamais de fausse enthousiasme systématique."
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
    focus_opp: Opportunity = None,
) -> str:
    """
    Chat avec contexte complet : profil + opportunités réelles + docs + candidatures
    (+ éventuellement une opportunité en focus, ouverte depuis sa page).
    """
    client = _get_client()
    system_prompt = _build_coach_system_prompt(user, opportunities=opportunities, context_data=context_data, focus_opp=focus_opp)

    messages = [{"role": "system", "content": system_prompt}]

    # Historique (max 12 messages = 6 échanges)
    for msg in history[-12:]:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": message})

    needs_search = _needs_fresh_info(message)
    model_to_use = COMPOUND_MODEL if needs_search else GROQ_MODEL

    if needs_search:
        # groq/compound "décide lui-même" s'il cherche ou non — pour une question
        # datée/factuelle on ne veut pas le laisser deviner, donc on le pousse
        # explicitement à utiliser sa recherche web plutôt que de répondre de mémoire.
        messages.append({
            "role": "system",
            "content": (
                "Cette question porte sur une information datée ou potentiellement récente. "
                "Utilise ta capacité de recherche web pour vérifier l'info actuelle avant de répondre — "
                "ne réponds pas de mémoire. Cite la source (nom du site) dans ta réponse. "
                "Si tu ne trouves pas l'info exacte pour cette année précise (ex: date d'ouverture "
                "pas encore annoncée), donne quand même l'information la plus utile que tu as trouvée "
                "(ex: dates des éditions précédentes, période habituelle d'ouverture) en précisant "
                "clairement que c'est une estimation basée sur les années passées — n'te contente "
                "JAMAIS de renvoyer juste vers le site officiel sans rien de concret, ce n'est pas une "
                "réponse utile pour l'étudiant."
            ),
        })

    try:
        completion = client.chat.completions.create(
            model=model_to_use,
            messages=messages,
            temperature=0.72,
            max_tokens=900,
        )
    except Exception as e:
        # Si groq/compound a un souci ponctuel, on retombe sur le modèle normal
        # plutôt que de casser le chat pour l'étudiant.
        if model_to_use == COMPOUND_MODEL:
            print(f"[Link IA] groq/compound indisponible, repli sur {GROQ_MODEL}. Détail : {e}")
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.72,
                max_tokens=900,
            )
        else:
            raise

    return completion.choices[0].message.content.strip()
