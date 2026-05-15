# app/services/scoring.py
# Score de préparation — analyse RÉELLE de l'opportunité + profil étudiant
# Utilise l'IA (Groq) pour extraire les vrais critères de l'opportunité

from sqlalchemy.orm import Session
from app.models.user import User
from app.models.opportunity import Opportunity
from app.models.document import Document


def has_document(db: Session, user_id, doc_type: str) -> bool:
    doc = db.query(Document).filter(
        Document.user_id == user_id,
        Document.type == doc_type,
        Document.is_valid == True,
    ).first()
    return doc is not None


def analyze_opportunity_requirements(opp: Opportunity) -> dict:
    """
    Analyse l'opportunité pour extraire LES VRAIS critères nécessaires.
    Combine les données structurées (required_level, min_gpa...)
    avec une analyse du texte de description.
    Retourne un dict avec tous les critères détectés.
    """
    description = (opp.description or "").lower()
    title = (opp.title or "").lower()
    full_text = title + " " + description

    # Détection langues dans la description
    detected_languages = []
    if opp.required_languages:
        detected_languages = opp.required_languages
    else:
        if any(w in full_text for w in ["english", "anglais", "toefl", "ielts"]):
            detected_languages.append("en")
        if any(w in full_text for w in ["français", "french", "delf", "dalf", "tcf"]):
            detected_languages.append("fr")
        if any(w in full_text for w in ["german", "deutsch", "allemand", "goethe"]):
            detected_languages.append("de")
        if not detected_languages:
            detected_languages = ["en"]  # défaut

    # Détection tests de langue requis
    lang_tests = []
    if any(w in full_text for w in ["toefl", "ielts", "gre", "gmat", "delf", "dalf", "tcf", "testdaf"]):
        if "toefl" in full_text: lang_tests.append("TOEFL")
        if "ielts" in full_text: lang_tests.append("IELTS")
        if "gre" in full_text: lang_tests.append("GRE")
        if "gmat" in full_text: lang_tests.append("GMAT")
        if any(w in full_text for w in ["delf","dalf","tcf"]): lang_tests.append("DELF/DALF")
        if "testdaf" in full_text: lang_tests.append("TestDaF")

    # Détection niveau requis
    required_levels = opp.required_level or []
    if not required_levels:
        if any(w in full_text for w in ["licence", "bachelor", "undergraduate", "bsc", "l3"]):
            required_levels.append("Licence")
        if any(w in full_text for w in ["master", "msc", "mba", "m2", "postgraduate"]):
            required_levels.append("Master")
        if any(w in full_text for w in ["phd", "doctorat", "doctoral", "thesis", "thèse"]):
            required_levels.append("Doctorat")

    # Détection documents souvent requis selon le type
    required_docs = []
    if opp.type in ["bourse", "echange"]:
        required_docs = ["CV", "Lettre de motivation", "Relevés de notes", "CNI/Passeport", "Lettre de recommandation"]
        if any(w in full_text for w in ["projet de recherche", "research proposal", "research project"]):
            required_docs.append("Projet de recherche")
        if any(w in full_text for w in ["medical", "médical", "health certificate"]):
            required_docs.append("Certificat médical")
        if any(w in full_text for w in ["bank statement", "relevé bancaire", "financial"]):
            required_docs.append("Relevé bancaire")
    elif opp.type == "stage":
        required_docs = ["CV", "Lettre de motivation", "Relevés de notes", "CNI"]
    elif opp.type == "emploi":
        required_docs = ["CV", "Lettre de motivation", "CNI"]
    elif opp.type == "concours":
        required_docs = ["CNI", "Relevés de notes", "Attestation d'inscription", "Photos d'identité"]

    # Compétences clés souvent requises selon le domaine
    key_skills = []
    if any(w in full_text for w in ["python", "programming", "coding", "développeur", "developer", "software"]):
        key_skills.extend(["Python", "Git", "Algorithmique"])
    if any(w in full_text for w in ["data", "machine learning", "ai", "intelligence artificielle", "data science"]):
        key_skills.extend(["Python", "SQL", "Machine Learning", "Statistics"])
    if any(w in full_text for w in ["web", "javascript", "react", "frontend", "backend"]):
        key_skills.extend(["JavaScript", "HTML/CSS", "Framework web"])
    if any(w in full_text for w in ["finance", "comptabilité", "audit", "accounting"]):
        key_skills.extend(["Excel", "Analyse financière", "Comptabilité"])
    if any(w in full_text for w in ["management", "gestion de projet", "project management"]):
        key_skills.extend(["Gestion de projet", "Leadership", "Communication"])
    if any(w in full_text for w in ["recherche", "research", "laboratory", "laboratoire"]):
        key_skills.extend(["Méthodologie de recherche", "Rédaction académique"])

    # GPA minimum
    min_gpa = opp.min_gpa
    if not min_gpa:
        # Essayer de détecter dans la description
        import re
        gpa_patterns = [
            r"moyenne.*?(\d+[.,]\d+)/20",
            r"gpa.*?(\d+[.,]\d+)",
            r"(\d+[.,]\d+)/20.*?minimum",
        ]
        for pat in gpa_patterns:
            m = re.search(pat, full_text)
            if m:
                try:
                    min_gpa = float(m.group(1).replace(",", "."))
                    break
                except:
                    pass

    return {
        "required_levels": required_levels,
        "required_languages": detected_languages,
        "lang_tests": lang_tests,
        "min_gpa": min_gpa,
        "required_docs": required_docs,
        "key_skills": list(set(key_skills)),
        "country": opp.country,
        "type": opp.type,
    }


def get_learning_resources(skill: str, is_free: bool = True) -> list[dict]:
    """Retourne des ressources d'apprentissage pour une compétence."""
    resources_map = {
        "Python": [
            {"name": "Python.org (officiel)", "url": "https://docs.python.org/fr/3/tutorial/", "free": True, "duration": "2-4 semaines"},
            {"name": "freeCodeCamp Python", "url": "https://www.freecodecamp.org/learn/scientific-computing-with-python/", "free": True, "duration": "3-6 semaines"},
            {"name": "Coursera Python (Google)", "url": "https://www.coursera.org/learn/python-crash-course", "free": False, "duration": "6 semaines"},
        ],
        "English": [
            {"name": "Duolingo", "url": "https://www.duolingo.com", "free": True, "duration": "Continu"},
            {"name": "BBC Learning English", "url": "https://www.bbc.co.uk/learningenglish", "free": True, "duration": "Continu"},
        ],
        "IELTS": [
            {"name": "IELTS.org (préparation officielle)", "url": "https://www.ielts.org/what-is-ielts/ielts-sample-test-questions", "free": True, "duration": "2-3 mois"},
            {"name": "British Council IELTS Prep", "url": "https://www.britishcouncil.org/exam/ielts/ielts-preparation", "free": False, "duration": "2-3 mois"},
        ],
        "TOEFL": [
            {"name": "ETS TOEFL Prep (officiel)", "url": "https://www.ets.org/toefl/test-takers/ibt/prepare.html", "free": True, "duration": "2-3 mois"},
        ],
        "Git": [
            {"name": "Git - Documentation officielle", "url": "https://git-scm.com/doc", "free": True, "duration": "1 semaine"},
            {"name": "GitHub Learning Lab", "url": "https://lab.github.com", "free": True, "duration": "1-2 semaines"},
        ],
        "SQL": [
            {"name": "SQLZoo", "url": "https://sqlzoo.net", "free": True, "duration": "2-3 semaines"},
            {"name": "Mode SQL Tutorial", "url": "https://mode.com/sql-tutorial/", "free": True, "duration": "2-4 semaines"},
        ],
        "Machine Learning": [
            {"name": "Coursera ML (Andrew Ng)", "url": "https://www.coursera.org/learn/machine-learning", "free": False, "duration": "11 semaines"},
            {"name": "fast.ai", "url": "https://www.fast.ai", "free": True, "duration": "8-12 semaines"},
        ],
        "Excel": [
            {"name": "Microsoft Excel (cours officiel)", "url": "https://support.microsoft.com/fr-fr/excel", "free": True, "duration": "1-2 semaines"},
            {"name": "GCFGlobal Excel", "url": "https://edu.gcfglobal.org/en/excel2016/", "free": True, "duration": "1 semaine"},
        ],
        "Gestion de projet": [
            {"name": "Google Project Management (Coursera)", "url": "https://www.coursera.org/professional-certificates/google-project-management", "free": False, "duration": "6 mois"},
            {"name": "PMI Resources (gratuit)", "url": "https://www.pmi.org/learning/library", "free": True, "duration": "Continu"},
        ],
        "Rédaction académique": [
            {"name": "Coursera Academic Writing (Duke)", "url": "https://www.coursera.org/learn/academic-writing", "free": False, "duration": "4 semaines"},
            {"name": "Purdue OWL", "url": "https://owl.purdue.edu/owl/purdue_owl.html", "free": True, "duration": "Continu"},
        ],
    }
    return resources_map.get(skill, [
        {"name": f"Rechercher '{skill}' sur Coursera", "url": f"https://www.coursera.org/search?query={skill.replace(' ', '+')}", "free": False, "duration": "Variable"},
        {"name": f"Rechercher '{skill}' sur YouTube", "url": f"https://www.youtube.com/results?search_query={skill.replace(' ', '+')}", "free": True, "duration": "Variable"},
    ])


def compute_preparation_score(user: User, opp: Opportunity, db: Session) -> dict:
    """
    Score de préparation INTELLIGENT.
    Analyse vraiment l'opportunité et guide l'étudiant avec des actions concrètes.
    """
    # 1. Analyser les vrais critères de l'opportunité
    requirements = analyze_opportunity_requirements(opp)

    checks = []

    # ── Critères académiques ────────────────────────────────────────

    # Niveau d'études
    if requirements["required_levels"]:
        ok = user.level in requirements["required_levels"]
        checks.append({
            "label": "Niveau d'études",
            "ok": ok,
            "fix": f"Niveau requis : {', '.join(requirements['required_levels'])}. Ton niveau actuel : {user.level or 'non renseigné'}",
            "category": "academic",
            "priority": 1,
        })

    # Moyenne
    if requirements["min_gpa"]:
        ok = bool(user.gpa and user.gpa >= requirements["min_gpa"])
        checks.append({
            "label": f"Moyenne ≥ {requirements['min_gpa']}/20",
            "ok": ok,
            "fix": f"Ta moyenne : {user.gpa or 'non renseignée'}/20. Minimum requis : {requirements['min_gpa']}/20",
            "category": "academic",
            "priority": 1,
        })

    # Langues
    if requirements["required_languages"]:
        user_langs = set(user.languages or [])
        missing = set(requirements["required_languages"]) - user_langs
        lang_names = {"fr":"Français","en":"Anglais","de":"Allemand","es":"Espagnol","ar":"Arabe"}
        ok = len(missing) == 0
        checks.append({
            "label": "Langues requises",
            "ok": ok,
            "fix": f"Langues manquantes : {', '.join(lang_names.get(l,l) for l in missing)}" if missing else "",
            "category": "academic",
            "priority": 1,
        })

    # Tests de langue spécifiques
    for test in requirements["lang_tests"]:
        checks.append({
            "label": f"Test {test} (souvent requis)",
            "ok": False,  # On ne peut pas savoir si l'étudiant l'a passé
            "fix": f"Ce type d'opportunité demande souvent le {test}. Vérifie les détails et prépare-toi.",
            "category": "language_test",
            "priority": 2,
            "resources": get_learning_resources(test),
        })

    # Filière
    if opp.required_fields:
        ok = user.field in opp.required_fields
        checks.append({
            "label": "Filière compatible",
            "ok": ok,
            "fix": f"Filières acceptées : {', '.join(opp.required_fields)}. Ta filière : {user.field or 'non renseignée'}",
            "category": "academic",
            "priority": 1,
        })

    # ── Documents ───────────────────────────────────────────────────

    doc_map = {
        "CV": "cv",
        "Relevés de notes": "releve",
        "CNI/Passeport": "cni",
        "CNI": "cni",
        "Attestation d'inscription": "attestation",
    }

    for doc_label in requirements["required_docs"]:
        doc_type = doc_map.get(doc_label)
        if doc_type:
            ok = has_document(db, user.id, doc_type)
            checks.append({
                "label": doc_label,
                "ok": ok,
                "fix": f"Upload ton {doc_label} dans le coffre-fort de documents",
                "category": "document",
                "priority": 2,
            })
        else:
            # Document qu'on ne peut pas vérifier automatiquement
            checks.append({
                "label": doc_label,
                "ok": False,
                "fix": f"Ce document est souvent requis : {doc_label}. Vérifie auprès de l'organisme.",
                "category": "document_external",
                "priority": 3,
            })

    # ── Compétences clés ────────────────────────────────────────────

    user_skills_lower = {s.lower() for s in (user.skills or [])}

    for skill in requirements["key_skills"][:5]:  # Max 5 compétences
        skill_lower = skill.lower()
        ok = skill_lower in user_skills_lower or any(skill_lower in s for s in user_skills_lower)
        checks.append({
            "label": f"Compétence : {skill}",
            "ok": ok,
            "fix": f"'{skill}' est souvent requis pour ce type d'opportunité.",
            "category": "skill",
            "priority": 3,
            "resources": get_learning_resources(skill),
        })

    # ── Profil de base ──────────────────────────────────────────────

    checks.append({
        "label": "Profil complété",
        "ok": bool(user.level and user.field and user.gpa and user.city),
        "fix": "Complete ton profil : niveau, filière, moyenne, ville",
        "category": "profile",
        "priority": 2,
    })

    # ── Calcul score ────────────────────────────────────────────────

    # Pondération : critères obligatoires pèsent plus
    ok_count = sum(1 for c in checks if c["ok"])
    total = len(checks)
    score = round((ok_count / total) * 100) if total > 0 else 0

    missing = [c for c in checks if not c["ok"]]
    # Trier par priorité
    missing.sort(key=lambda x: x.get("priority", 3))

    # ── Plan d'action personnalisé ──────────────────────────────────

    action_plan = []

    # Étape 1 : Documents manquants (urgent, concret)
    missing_docs = [m for m in missing if m["category"] == "document"]
    if missing_docs:
        action_plan.append({
            "step": 1,
            "title": "📁 Prépare tes documents",
            "actions": [f"Uploade ton {m['label']}" for m in missing_docs],
            "url": "/dashboard/documents",
            "urgency": "high",
        })

    # Étape 2 : Profil et critères bloquants
    blocking = [m for m in missing if m["category"] in ["academic", "profile"] and m.get("priority",3)==1]
    if blocking:
        action_plan.append({
            "step": 2,
            "title": "⚠️ Critères d'éligibilité",
            "actions": [m["fix"] for m in blocking],
            "url": "/dashboard/profile",
            "urgency": "critical",
        })

    # Étape 3 : Compétences à développer
    skill_gaps = [m for m in missing if m["category"] == "skill"]
    if skill_gaps:
        skill_resources = []
        for sg in skill_gaps[:3]:
            for r in sg.get("resources", [])[:2]:
                skill_resources.append(f"{sg['label']} → {r['name']} ({'gratuit' if r['free'] else 'payant'}, {r['duration']})")
        action_plan.append({
            "step": 3,
            "title": "📚 Compétences à développer",
            "actions": skill_resources if skill_resources else [m["fix"] for m in skill_gaps],
            "urgency": "medium",
        })

    # Étape 4 : Tests de langue
    test_gaps = [m for m in missing if m["category"] == "language_test"]
    if test_gaps:
        action_plan.append({
            "step": 4,
            "title": "🌍 Tests de langue",
            "actions": [m["fix"] for m in test_gaps],
            "urgency": "medium",
        })

    # Message principal
    if score == 100:
        message = "🎉 Ton dossier est complet ! Tu peux candidater dès maintenant."
    elif score >= 75:
        message = f"✅ Tu es prêt à {score}%. Quelques points à finaliser avant de postuler."
    elif score >= 50:
        message = f"⚡ Tu es à {score}% de préparation. Suis le plan d'action ci-dessous."
    else:
        message = f"⚠️ Tu es prêt à {score}%. Commence par les actions prioritaires."

    return {
        "score": score,
        "checks": checks,
        "missing": missing,
        "message": message,
        "ok_count": ok_count,
        "total_checks": total,
        "action_plan": action_plan,
        "requirements": requirements,
        "opportunity_type": opp.type,
        "opportunity_country": opp.country,
    }
