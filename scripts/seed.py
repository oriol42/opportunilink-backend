import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal
from app.models.opportunity import Opportunity
from datetime import date

db = SessionLocal()

opps = [
    dict(title="Bourse Eiffel Excellence - France 2026", type="bourse", description="La bourse Eiffel finance des Masters et Doctorats d excellence en France. Allocation mensuelle, billet d avion et assurance inclus.", source_url="https://www.campusfrance.org/fr/bourse-eiffel", deadline=date(2026, 8, 15), country="France", required_level=["Master","Doctorat"], required_fields=["Informatique","Ingenierie","Economie"], required_languages=["fr"], min_gpa=14.0, reliability_score=95, is_verified=True),
    dict(title="Stage Developpeur MTN Cameroun", type="stage", description="MTN Cameroun recrute des stagiaires developpeurs pour son equipe Digital. Stack Python et JavaScript. Duree 6 mois, indemnite competitive.", source_url="https://www.mtn.cm/carrieres", deadline=date(2026, 6, 30), country="Cameroun", required_level=["Licence","Master","Ingenieur"], required_fields=["Informatique"], required_languages=["fr","en"], min_gpa=12.0, reliability_score=90, is_verified=True),
    dict(title="DAAD Helmut Schmidt Programme", type="bourse", description="Bourse allemande pour futurs leaders africains. Master en politiques publiques a Hambourg. Allocation mensuelle, vols et assurance.", source_url="https://www.daad.de/helmut-schmidt", deadline=date(2026, 7, 31), country="Allemagne", required_level=["Master"], required_fields=["Droit","Economie","Gestion"], required_languages=["en"], min_gpa=13.0, reliability_score=98, is_verified=True),
    dict(title="Google Africa Developer Scholarship", type="bourse", description="Google finance des formations developpeurs pour africains. Android, Web, Cloud. 100% en ligne, certificat reconnu, mentorat inclus.", source_url="https://developers.google.com/africa", deadline=date(2026, 8, 31), country="En ligne", required_level=["Licence","Master","BTS"], required_fields=["Informatique"], required_languages=["en"], min_gpa=None, reliability_score=93, is_verified=True),
    dict(title="Erasmus+ Mobilite Etudiante Afrique", type="echange", description="Erasmus+ finance des mobilites de 3 a 12 mois dans des universites europeennes. Bourse mensuelle, frais de voyage et assurance couverts.", source_url="https://erasmus-plus.ec.europa.eu", deadline=date(2026, 10, 15), country="Europe", required_level=["Licence","Master"], required_fields=[], required_languages=["fr","en"], min_gpa=13.0, reliability_score=95, is_verified=True),
    dict(title="Stage Finance - Societe Generale Cameroun", type="stage", description="Stage de 3 a 6 mois en direction financiere. Analyse financiere, reporting Excel. Formation aux outils bancaires, possibilite d embauche.", source_url="https://www.societegenerale.cm/carrieres", deadline=date(2026, 6, 15), country="Cameroun", required_level=["Licence","Master"], required_fields=["Economie","Gestion"], required_languages=["fr"], min_gpa=13.0, reliability_score=88, is_verified=False),
    dict(title="Concours ENS Yaounde - Recrutement Enseignants", type="concours", description="ENS Yaounde recrute pour la formation d enseignants du secondaire. Toutes disciplines. Bourse pendant la formation et emploi garanti.", source_url="https://www.ens.cm", deadline=date(2026, 7, 1), country="Cameroun", required_level=["Licence","Master"], required_fields=[], required_languages=["fr"], min_gpa=12.0, reliability_score=85, is_verified=False),
    dict(title="Bourse AUF Doctorat en Cotutelle", type="bourse", description="L AUF finance des doctorats en cotutelle entre universites africaines et europeennes. Allocation mensuelle et mobilite internationale.", source_url="https://www.auf.org/bourses-doctorat", deadline=date(2026, 9, 1), country="France", required_level=["Doctorat"], required_fields=[], required_languages=["fr"], min_gpa=14.0, reliability_score=92, is_verified=True),
]

inserted = 0
for data in opps:
    exists = db.query(Opportunity).filter(Opportunity.source_url == data["source_url"]).first()
    if exists:
        print(f"Ignore : {data['title']}")
        continue
    db.add(Opportunity(id=uuid.uuid4(), is_active=True, is_scraped=False, **data))
    inserted += 1
    print(f"OK : {data['title']}")

db.commit()
db.close()
print(f"\n{inserted} opportunites inserees.")
