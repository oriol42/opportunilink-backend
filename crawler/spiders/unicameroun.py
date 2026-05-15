# Universités camerounaises — concours d'entrée et admissions
import scrapy, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider

class UniCamerounSpider(BaseOpportunitySpider):
    name = "unicameroun"
    custom_settings = { "DOWNLOAD_DELAY": 3, "ROBOTSTXT_OBEY": True }

    # Données structurées sur les concours camerounais (stables chaque année)
    CONCOURS = [
        {
            "title": "Concours d'entrée École Polytechnique de Yaoundé (ENSPY) 2026",
            "url": "https://www.polytechnique.cm",
            "description": "L'École Nationale Supérieure Polytechnique de Yaoundé organise son concours d'entrée annuel. Filières : Génie Civil, Génie Électrique, Génie Informatique, Génie Mécanique, Génie Chimique. Conditions : Baccalauréat C, D ou E avec mention, ou équivalent. Formation de 5 ans menant au diplôme d'ingénieur.",
            "level": ["Ingénieur"], "field": ["Informatique","Ingénierie Civile","Mécanique","Électronique"],
        },
        {
            "title": "Concours d'entrée ESSEC Douala (École de Commerce) 2026",
            "url": "https://www.essec.cm",
            "description": "L'ESSEC de Douala recrute pour ses programmes Bachelor et Master en Commerce, Marketing, Finance et Management. Concours sur dossier et test écrit. Bourses disponibles pour les meilleurs candidats.",
            "level": ["Licence","Master"], "field": ["Gestion","Finance","Marketing","Économie"],
        },
        {
            "title": "Concours IRIC (Relations Internationales et Coopération) Yaoundé 2026",
            "url": "https://www.iric.cm",
            "description": "L'Institut des Relations Internationales du Cameroun organise son concours annuel pour la formation de diplomates et spécialistes en relations internationales. Programme de 2 ans. Conditions : Licence minimum, niveau BAC+3.",
            "level": ["Master"], "field": ["Droit","Sciences Politiques","Relations Internationales"],
        },
        {
            "title": "Concours ENAM (Administration) Yaoundé 2026",
            "url": "https://www.enam.cm",
            "description": "L'École Nationale d'Administration et de Magistrature recrute pour la formation de hauts fonctionnaires et magistrats. Sections : Administration générale, Magistrature, Diplomatie, Gestion. Emploi garanti dans la fonction publique.",
            "level": ["Licence","Master"], "field": ["Droit","Économie","Gestion","Sciences Politiques"],
        },
        {
            "title": "Admission Master Recherche Université de Yaoundé I 2026",
            "url": "https://www.uy1.uninet.cm",
            "description": "L'Université de Yaoundé I ouvre les candidatures pour ses Masters de Recherche dans les domaines des Sciences, Lettres et Sciences Humaines. Bourse de recherche possible pour les meilleurs dossiers. Conditions : Licence avec mention Bien ou Très Bien.",
            "level": ["Master"], "field": ["Informatique","Sciences","Mathématiques","Lettres & Sciences Humaines"],
        },
        {
            "title": "Programme Doctoral FASA (Agronomie) Université de Dschang 2026",
            "url": "https://www.univ-dschang.org",
            "description": "La Faculté d'Agronomie et des Sciences Agricoles de l'Université de Dschang recrute des doctorants. Bourses de recherche disponibles. Domaines : Agriculture, Élevage, Environnement, Agroalimentaire.",
            "level": ["Doctorat"], "field": ["Agriculture","Environnement","Sciences"],
        },
    ]

    def start_requests(self):
        for c in self.CONCOURS:
            yield scrapy.Request(c["url"], callback=self.parse_concours, meta={"concours": c}, dont_filter=True)

    def parse_concours(self, response):
        c = response.meta["concours"]
        yield self.make_opportunity_item(
            title=c["title"], description=c["description"], source_url=c["url"],
            deadline=None, country="Cameroun", opp_type="concours",
            required_level=c["level"], required_fields=c["field"], required_languages=["fr"], min_gpa=None,
        )
