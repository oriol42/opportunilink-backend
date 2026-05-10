"""
Script de seed — peuple la DB avec des opportunités réelles 2026.
Lance avec : python scripts/seed.py
"""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal
from app.models.opportunity import Opportunity
from datetime import date

db = SessionLocal()

OPPORTUNITIES = [
    # ── Bourses ──────────────────────────────────────────────────
    dict(
        title="Bourse Eiffel Excellence — France 2026",
        type="bourse",
        description="La bourse Eiffel finance des Masters et Doctorats d'excellence en France. Allocation mensuelle 1181€, billet d'avion, assurance maladie inclus. Ouverte aux étudiants des pays en développement.",
        source_url="https://www.campusfrance.org/fr/bourse-eiffel",
        deadline=date(2026, 9, 15),
        country="France",
        required_level=["Master", "Doctorat"],
        required_fields=["Informatique", "Ingénierie", "Économie", "Droit"],
        required_languages=["fr"],
        min_gpa=14.0,
        reliability_score=98,
        is_verified=True,
    ),
    dict(
        title="DAAD Helmut Schmidt Programme 2026",
        type="bourse",
        description="Bourse allemande pour futurs leaders africains. Master en politiques publiques et gestion à Hambourg. Allocation mensuelle 850€, billets d'avion, assurance, cours d'allemand inclus.",
        source_url="https://www.daad.de/helmut-schmidt",
        deadline=date(2026, 7, 31),
        country="Allemagne",
        required_level=["Master"],
        required_fields=["Économie", "Gestion", "Droit", "Sciences Politiques"],
        required_languages=["en"],
        min_gpa=13.0,
        reliability_score=98,
        is_verified=True,
    ),
    dict(
        title="Bourse AUF Doctorat en Cotutelle 2026",
        type="bourse",
        description="L'AUF finance des doctorats en cotutelle entre universités africaines et européennes. Allocation mensuelle, mobilité internationale prise en charge. Ouvert aux filières scientifiques et humaines.",
        source_url="https://www.auf.org/bourses-doctorat",
        deadline=date(2026, 9, 1),
        country="France",
        required_level=["Doctorat"],
        required_fields=[],
        required_languages=["fr"],
        min_gpa=14.0,
        reliability_score=92,
        is_verified=True,
    ),
    dict(
        title="Google Africa Developer Scholarship 2026",
        type="bourse",
        description="Google finance des formations développeurs pour étudiants africains. Tracks : Android, Web, Cloud. 100% en ligne, certificat reconnu par l'industrie, mentorat par des ingénieurs Google inclus.",
        source_url="https://developers.google.com/africa",
        deadline=date(2026, 8, 31),
        country="En ligne",
        required_level=["Licence", "Master", "BTS"],
        required_fields=["Informatique"],
        required_languages=["en"],
        min_gpa=None,
        reliability_score=95,
        is_verified=True,
    ),
    dict(
        title="Erasmus+ Mobilité Étudiante Afrique 2026-2027",
        type="echange",
        description="Erasmus+ finance des mobilités de 3 à 12 mois dans des universités européennes partenaires. Bourse mensuelle 700-850€, frais de voyage et assurance couverts. Retour au pays d'origine obligatoire.",
        source_url="https://erasmus-plus.ec.europa.eu",
        deadline=date(2026, 10, 15),
        country="Europe",
        required_level=["Licence", "Master"],
        required_fields=[],
        required_languages=["fr", "en"],
        min_gpa=13.0,
        reliability_score=96,
        is_verified=True,
    ),
    dict(
        title="Bourse MasterCard Foundation — Universités Africaines 2026",
        type="bourse",
        description="La MasterCard Foundation finance des masters complets dans les meilleures universités africaines et internationales. Couverture totale : frais de scolarité, logement, billet d'avion, allocation mensuelle.",
        source_url="https://mastercardfdn.org/scholarships",
        deadline=date(2026, 11, 30),
        country="International",
        required_level=["Master"],
        required_fields=[],
        required_languages=["en", "fr"],
        min_gpa=14.0,
        reliability_score=95,
        is_verified=True,
    ),

    # ── Stages ───────────────────────────────────────────────────
    dict(
        title="Stage Développeur Python — MTN Cameroun 2026",
        type="stage",
        description="MTN Cameroun recrute des stagiaires développeurs Python pour son équipe Digital & Innovation. Stack : Python, Django, REST APIs, PostgreSQL. Durée 6 mois, indemnité compétitive, possibilité d'embauche.",
        source_url="https://www.mtn.cm/carrieres",
        deadline=date(2026, 6, 30),
        country="Cameroun",
        required_level=["Licence", "Master", "Ingénieur"],
        required_fields=["Informatique"],
        required_languages=["fr", "en"],
        min_gpa=12.0,
        reliability_score=90,
        is_verified=True,
    ),
    dict(
        title="Stage Finance & Analyse — Société Générale Cameroun",
        type="stage",
        description="Stage de 3 à 6 mois en direction financière. Missions : analyse financière, reporting Excel/Power BI, suivi de portefeuille. Formation aux outils bancaires, possibilité d'embauche CDI.",
        source_url="https://www.societegenerale.cm/carrieres",
        deadline=date(2026, 7, 15),
        country="Cameroun",
        required_level=["Licence", "Master"],
        required_fields=["Économie", "Gestion"],
        required_languages=["fr"],
        min_gpa=13.0,
        reliability_score=88,
        is_verified=False,
    ),
    dict(
        title="Stage Data Analyst — Orange Cameroun",
        type="stage",
        description="Orange Cameroun recherche un(e) stagiaire Data Analyst pour son équipe Business Intelligence. Outils : Python, SQL, Tableau, Power BI. Durée : 3-6 mois. Indemnité + avantages Orange.",
        source_url="https://www.orange.cm/fr/carrieres",
        deadline=date(2026, 7, 1),
        country="Cameroun",
        required_level=["Licence", "Master"],
        required_fields=["Informatique", "Mathématiques", "Statistiques"],
        required_languages=["fr", "en"],
        min_gpa=12.0,
        reliability_score=88,
        is_verified=False,
    ),
    dict(
        title="Stage Ingénieur Réseaux — Camtel 2026",
        type="stage",
        description="Camtel recrute un stagiaire ingénieur réseaux pour son département technique. Missions : configuration équipements Cisco, supervision réseau, documentation. Durée 4-6 mois, Yaoundé.",
        source_url="https://www.camtel.cm/recrutement",
        deadline=date(2026, 8, 15),
        country="Cameroun",
        required_level=["Ingénieur", "Master"],
        required_fields=["Informatique", "Télécommunications"],
        required_languages=["fr"],
        min_gpa=12.0,
        reliability_score=82,
        is_verified=False,
    ),

    # ── Emplois ──────────────────────────────────────────────────
    dict(
        title="Junior Software Engineer — Andela (Remote Africa)",
        type="emploi",
        description="Andela recrute des développeurs juniors pour des missions remote avec des entreprises américaines et européennes. Stack flexible : Python, JavaScript, Java. Salaire en USD. Formation Andela incluse.",
        source_url="https://andela.com/careers",
        deadline=date(2026, 12, 31),
        country="Remote (International)",
        required_level=["Licence", "Master"],
        required_fields=["Informatique"],
        required_languages=["en"],
        min_gpa=None,
        reliability_score=88,
        is_verified=False,
    ),
    dict(
        title="Chargé de Programme — UNICEF Cameroun",
        type="emploi",
        description="UNICEF Cameroun recherche un chargé de programme pour son bureau de Yaoundé. Missions : suivi de projets éducation/santé, rédaction rapports, coordination partenaires. Contrat 1 an renouvelable.",
        source_url="https://www.unicef.org/careers",
        deadline=date(2026, 8, 30),
        country="Cameroun",
        required_level=["Master"],
        required_fields=["Sciences Sociales", "Droit", "Santé Publique", "Gestion"],
        required_languages=["fr", "en"],
        min_gpa=13.0,
        reliability_score=95,
        is_verified=True,
    ),

    # ── Concours ─────────────────────────────────────────────────
    dict(
        title="Concours ENS Yaoundé — Recrutement Enseignants 2026",
        type="concours",
        description="L'École Normale Supérieure de Yaoundé ouvre son concours d'entrée pour la formation d'enseignants du secondaire toutes disciplines. Bourse pendant la formation (3 ans), emploi garanti à la sortie.",
        source_url="https://www.ens.cm/concours",
        deadline=date(2026, 8, 1),
        country="Cameroun",
        required_level=["Licence", "Master"],
        required_fields=[],
        required_languages=["fr"],
        min_gpa=12.0,
        reliability_score=85,
        is_verified=False,
    ),
    dict(
        title="Prix Jeune Entrepreneur Africain — Tony Elumelu Foundation 2026",
        type="concours",
        description="La Fondation Tony Elumelu sélectionne 1000 jeunes entrepreneurs africains. Chaque lauréat reçoit 5000 USD de seed capital, 12 semaines de formation business, mentorat personnalisé.",
        source_url="https://www.tonyelumelufoundation.org",
        deadline=date(2026, 6, 1),
        country="International",
        required_level=["Licence", "Master", "BTS"],
        required_fields=[],
        required_languages=["en", "fr"],
        min_gpa=None,
        reliability_score=92,
        is_verified=True,
    ),
]

inserted = 0
skipped = 0
for data in OPPORTUNITIES:
    exists = db.query(Opportunity).filter(
        Opportunity.source_url == data["source_url"]
    ).first()
    if exists:
        # Mettre à jour la deadline si elle a changé
        if exists.deadline != data["deadline"]:
            exists.deadline = data["deadline"]
            db.commit()
            print(f"  ↺ Deadline mise à jour : {data['title'][:50]}")
        else:
            print(f"  — Existe déjà : {data['title'][:50]}")
        skipped += 1
        continue

    db.add(Opportunity(
        id=uuid.uuid4(),
        is_active=True,
        is_scraped=False,
        **data,
    ))
    db.commit()
    inserted += 1
    print(f"  ✓ {data['title'][:60]}")

db.close()
print(f"\n{'='*50}")
print(f"  Insertées : {inserted}")
print(f"  Ignorées  : {skipped}")
print(f"  Total     : {inserted + skipped}")
