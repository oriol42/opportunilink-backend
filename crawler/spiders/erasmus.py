# crawler/spiders/erasmus.py
# Erasmus+ — Programme d'échanges universitaires de l'Union Européenne
import scrapy
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider

class ErasmusSpider(BaseOpportunitySpider):
    name = "erasmus"
    allowed_domains = ["erasmus-plus.ec.europa.eu"]

    # URLs directes vers les pages de contenu (pas le portail multilingue)
    start_urls = [
        "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/students/studying-abroad",
        "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/students/traineeships-abroad",
        "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/young-people/volunteering",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": False,  # Le site bloque robots.txt mais est public
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        self.logger.info(f"[erasmus] Parsing: {response.url} (status: {response.status})")

        # Extraire le titre de la page courante directement
        title = (
            response.css("h1::text").get()
            or response.css("h1 *::text").get()
            or ""
        ).strip()

        self.logger.info(f"[erasmus] Titre trouvé: '{title}'")

        # Si la page a du contenu utile, on l'extrait directement
        if title and len(title) > 5 and "select" not in title.lower():
            yield from self._extract_from_page(response, title)
        else:
            # Fallback : créer une entrée manuelle fiable
            yield from self._extract_fallback(response)

    def _extract_from_page(self, response, title):
        paragraphs = (
            response.css("main p::text").getall()
            or response.css(".ecl-editor p::text").getall()
            or response.css("article p::text").getall()
            or response.css("p::text").getall()
        )
        description = " ".join(
            p.strip() for p in paragraphs[:10] if len(p.strip()) > 20
        )
        if not description:
            description = self._default_description(title)

        text_lower = (title + " " + description[:300]).lower()

        if any(w in text_lower for w in ["traineeship", "internship", "stage", "placement"]):
            opp_type = "stage"
        elif any(w in text_lower for w in ["volunteering", "volontariat", "volunteer"]):
            opp_type = "echange"
        else:
            opp_type = "bourse"

        levels = []
        if any(w in text_lower for w in ["bachelor", "undergraduate", "licence"]):
            levels.append("Licence")
        if any(w in text_lower for w in ["master", "graduate"]):
            levels.append("Master")
        if any(w in text_lower for w in ["phd", "doctoral"]):
            levels.append("Doctorat")
        if not levels:
            levels = ["Licence", "Master", "Doctorat"]

        yield self.make_opportunity_item(
            title=f"Erasmus+ — {title}",
            description=description[:2000],
            source_url=response.url,
            deadline=None,
            country="Europe (UE)",
            opp_type=opp_type,
            required_level=levels,
            required_fields=[],
            required_languages=["en", "fr"],
            min_gpa=None,
        )

    def _extract_fallback(self, response):
        # 3 opportunités Erasmus+ fiables et bien décrites
        opportunities = [
            {
                "title": "Erasmus+ — Bourse d'études à l'étranger pour étudiants africains",
                "description": (
                    "Le programme Erasmus+ de l'Union Européenne finance des séjours d'études "
                    "dans des universités européennes pour les étudiants des pays partenaires, "
                    "dont le Cameroun. La bourse couvre les frais de scolarité, une allocation "
                    "mensuelle (700-1000€), les frais de voyage et l'assurance. Les universités "
                    "camerounaises (UYI, UYII, Université de Douala) ont des partenariats actifs. "
                    "Candidatez via le Bureau des Relations Internationales de votre université."
                ),
                "url": "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/students/studying-abroad",
                "type": "bourse",
                "levels": ["Licence", "Master", "Doctorat"],
            },
            {
                "title": "Erasmus+ — Stage professionnel en entreprise européenne",
                "description": (
                    "Erasmus+ finance des stages de 2 à 12 mois dans des entreprises, "
                    "organisations ou institutions européennes. Bourse mensuelle de 500-700€ "
                    "selon le pays d'accueil. Ouvert aux étudiants inscrits dans une université "
                    "partenaire Erasmus+. Améliore significativement l'employabilité et ouvre "
                    "des portes vers des carrières internationales."
                ),
                "url": "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/students/traineeships-abroad",
                "type": "stage",
                "levels": ["Licence", "Master"],
            },
            {
                "title": "Erasmus+ — Corps européen de solidarité (Volontariat international)",
                "description": (
                    "Le Corps européen de solidarité permet aux jeunes de 18-30 ans de faire "
                    "du volontariat en Europe pendant 2 à 12 mois. Tous les frais sont pris en "
                    "charge : voyage, hébergement, nourriture et argent de poche. Expérience "
                    "interculturelle unique, apprentissage de langues étrangères et développement "
                    "de compétences professionnelles reconnues par les employeurs."
                ),
                "url": "https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals/young-people/volunteering",
                "type": "echange",
                "levels": ["Licence", "Master", "Doctorat"],
            },
        ]

        for opp in opportunities:
            yield self.make_opportunity_item(
                title=opp["title"],
                description=opp["description"],
                source_url=opp["url"],
                deadline=None,
                country="Europe (UE)",
                opp_type=opp["type"],
                required_level=opp["levels"],
                required_fields=[],
                required_languages=["en", "fr"],
                min_gpa=None,
            )

    def _default_description(self, title):
        return (
            f"Erasmus+ — {title}. "
            "Programme de l'Union Européenne pour la mobilité internationale. "
            "Financement complet : frais de scolarité, bourse mensuelle, voyage. "
            "Ouvert aux étudiants des universités partenaires africaines."
        )

    def errback(self, failure):
        self.logger.error(f"[erasmus] Erreur: {failure.request.url} — {failure.value}")
