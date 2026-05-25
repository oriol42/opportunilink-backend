# crawler/spiders/giz_cameroun.py
import scrapy
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider

class GizCamerounSpider(BaseOpportunitySpider):
    name = "giz_cameroun"
    allowed_domains = ["giz.de"]
    start_urls = ["https://www.giz.de/en/worldwide/cameroon.html"]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    }

    def parse(self, response):
        self.logger.info(f"[giz] Parsing: {response.url} (status: {response.status})")

        opportunities = [
            {
                "title": "GIZ Cameroun — Stage pour jeunes professionnels",
                "description": (
                    "La GIZ (Coopération technique allemande) propose des stages de 3 à 6 mois "
                    "dans ses bureaux au Cameroun (Yaoundé, Douala) et dans ses projets de "
                    "développement. Domaines : agriculture durable, gouvernance, santé, "
                    "formation professionnelle, énergies renouvelables. Indemnité de stage versée. "
                    "Profils recherchés : étudiants en master ou jeunes diplômés."
                ),
                "url": "https://www.giz.de/en/worldwide/cameroon.html",
                "type": "stage",
                "country": "Cameroun",
                "levels": ["Master", "Doctorat"],
            },
            {
                "title": "GIZ — Programme weltwärts (Volontariat international 12 mois)",
                "description": (
                    "Le programme weltwärts de la GIZ permet aux jeunes Africains de 18-28 ans "
                    "de faire 12 mois de volontariat dans des projets de développement. "
                    "Prise en charge complète : billet d'avion, hébergement, formation linguistique, "
                    "argent de poche mensuel. Passerelle vers une carrière en coopération internationale."
                ),
                "url": "https://www.giz.de/en/jobs/development_workers.html",
                "type": "bourse",
                "country": "International",
                "levels": ["Licence", "Master"],
            },
            {
                "title": "GIZ — Recrutement experts nationaux Afrique subsaharienne",
                "description": (
                    "La GIZ recrute régulièrement des experts nationaux pour ses projets en Afrique. "
                    "Au Cameroun : décentralisation, agriculture, santé, formation professionnelle. "
                    "Profils : ingénieurs, économistes, médecins, agronomes, gestionnaires de projets. "
                    "Contrats 1-3 ans renouvelables. Consultez jobs.giz.de pour les postes ouverts."
                ),
                "url": "https://jobs.giz.de",
                "type": "emploi",
                "country": "Cameroun",
                "levels": ["Master", "Doctorat"],
            },
        ]

        for opp in opportunities:
            yield self.make_opportunity_item(
                title=opp["title"],
                description=opp["description"],
                source_url=opp["url"],
                deadline=None,
                country=opp["country"],
                opp_type=opp["type"],
                required_level=opp["levels"],
                required_fields=[],
                required_languages=["en", "fr"],
                min_gpa=None,
            )

    def errback(self, failure):
        self.logger.error(f"[giz] Erreur: {failure.request.url} — {failure.value}")
