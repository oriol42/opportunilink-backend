"""
Script de test JETABLE — verifie que gpt-oss-120b classe correctement
une opportunite AVANT le prochain run Celery de 3h.
Ne touche PAS a la base de donnees. A supprimer apres usage.
"""
import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

from app.services.scoring import extract_requirements_from_description
from app.config import settings


class FakeOpportunity:
    """Objet minimal qui imite Opportunity — la fonction n'utilise que ces champs."""
    def __init__(self):
        self.id = "test-fake-001"
        self.required_docs = None  # force un vrai appel API (pas de cache)
        self.description = (
            "Bourse d'excellence pour etudiants en Master ou Doctorat en "
            "Informatique ou Intelligence Artificielle. Ouverte aux femmes "
            "uniquement. Le dossier doit inclure : releve de notes, CNI, "
            "extrait de casier judiciaire de moins de 3 mois, lettre de "
            "motivation, et un certificat TOEFL ou IELTS. Niveau requis : "
            "Master 2 minimum. Delai de candidature : 30 jours."
        )
        self.title = "Bourse d'excellence Femmes en IA 2026"
        self.type = "bourse"
        self.country = "France"


def run_test(label: str, use_backfill: bool):
    print(f"\n{'='*60}\n{label}\n{'='*60}")
    opp = FakeOpportunity()
    result = extract_requirements_from_description(opp, use_backfill_key=use_backfill)

    print(f"ai_extracted     : {result.get('ai_extracted')}")
    print(f"required_docs    : {result.get('required_docs')}")
    print(f"specific_documents: {result.get('specific_documents')}")
    print(f"target_fields    : {result.get('target_fields')}")
    print(f"target_gender    : {result.get('target_gender')}")
    print(f"lang_tests       : {result.get('lang_tests')}")

    if result.get("ai_extracted") is False:
        print("\n⚠️  ECHEC : le fallback par defaut a ete utilise. "
              "Regarde le message 'WARNING' juste au-dessus (imprime par logging) "
              "pour voir l'erreur exacte de Groq.")
    elif result.get("target_gender") != "femmes":
        print("\n⚠️  SUSPECT : la description dit explicitement 'femmes uniquement' "
              f"mais le modele a repondu '{result.get('target_gender')}'. "
              "A verifier manuellement.")
    else:
        print("\n✅ OK : extraction correcte.")


print(f"Cle principale configuree     : {bool(settings.groq_api_key)}")
print(f"Cle backfill configuree       : {bool(settings.groq_api_key_backfill)}")

run_test("TEST 1 — cle principale (comme Link IA / chat)", use_backfill=False)

if settings.groq_api_key_backfill:
    run_test("TEST 2 — cle backfill (comme la tache nocturne 3h)", use_backfill=True)
else:
    print("\n(Pas de cle backfill configuree localement — test 2 saute.)")
