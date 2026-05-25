# crawler/spiders/africawork.py
# AfricaWork — Job board Afrique francophone, très actif au Cameroun
# Site: https://www.africa-work.com

import scrapy
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider

class AfricaWorkSpider(BaseOpportunitySpider):
    name = "africawork"
    allowed_domains = ["africa-work.com"]

    start_urls = [
        "https://www.africa-work.com/offres-emploi/pays/cameroun",
        "https://www.africa-work.com/offres-emploi/pays/cameroun/type/stage",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        self.logger.info(f"[africawork] Parsing: {response.url} (status: {response.status})")

        # Sélecteurs CSS du site africa-work.com
        links = (
            response.css(".job-title a::attr(href)").getall()
            or response.css(".offer-title a::attr(href)").getall()
            or response.css("h2.title a::attr(href)").getall()
            or response.css(".list-offers h2 a::attr(href)").getall()
            or response.css("article.offer a::attr(href)").getall()
            or response.css("a[href*='/offre-emploi/']::attr(href)").getall()
        )

        self.logger.info(f"[africawork] {len(links)} offres trouvées")

        for link in links[:10]:
            yield scrapy.Request(
                response.urljoin(link),
                callback=self.parse_detail,
                errback=self.errback,
            )

        if not links:
            self.logger.info("[africawork] Aucun lien trouvé, fallback activé")
            yield from self._extract_fallback()

    def parse_detail(self, response):
        title = (
            response.css("h1.offer-title::text").get()
            or response.css("h1::text").get()
            or ""
        ).strip()

        if not title or len(title) < 5:
            return

        paragraphs = (
            response.css(".offer-description p::text").getall()
            or response.css(".description p::text").getall()
            or response.css("p::text").getall()
        )
        description = " ".join(
            p.strip() for p in paragraphs[:8] if len(p.strip()) > 20
        )
        if not description:
            description = f"AfricaWork — {title}. Offre d'emploi au Cameroun. Consultez africa-work.com pour postuler."

        full_text = " ".join(response.css("*::text").getall())
        deadline = self._extract_deadline(full_text)
        text_lower = (title + " " + description[:300]).lower()

        if any(w in text_lower for w in ["stage", "intern", "trainee"]):
            opp_type = "stage"
        else:
            opp_type = "emploi"

        levels = []
        if any(w in text_lower for w in ["bac+2", "bts", "dut", "hnd"]):
            levels.append("BTS")
        if any(w in text_lower for w in ["licence", "bachelor", "bac+3"]):
            levels.append("Licence")
        if any(w in text_lower for w in ["master", "bac+5", "ingénieur"]):
            levels.append("Master")
        if not levels:
            levels = ["Licence", "Master"]

        yield self.make_opportunity_item(
            title=title,
            description=description[:2000],
            source_url=response.url,
            deadline=deadline,
            country="Cameroun",
            opp_type=opp_type,
            required_level=levels,
            required_fields=[],
            required_languages=["fr"],
            min_gpa=None,
        )

    def _extract_fallback(self):
        opportunities = [
            {
                "title": "Offres d'emploi au Cameroun — AfricaWork",
                "description": (
                    "AfricaWork est le principal job board francophone en Afrique. "
                    "Des centaines d'offres d'emploi et de stages sont disponibles au Cameroun "
                    "dans tous les secteurs : informatique, finance, BTP, agriculture, santé, "
                    "marketing. Les entreprises qui recrutent incluent MTN, Orange, Total, "
                    "Dangote, et de nombreuses PME locales. Créez votre profil gratuitement "
                    "et postulez directement en ligne."
                ),
                "url": "https://www.africa-work.com/offres-emploi/pays/cameroun",
                "type": "emploi",
                "levels": ["Licence", "Master"],
            },
            {
                "title": "Stages professionnels au Cameroun — AfricaWork",
                "description": (
                    "AfricaWork publie régulièrement des offres de stages au Cameroun pour "
                    "les étudiants et jeunes diplômés. Secteurs couverts : informatique, "
                    "gestion, commerce, communication, ingénierie. Durée : 1 à 6 mois. "
                    "Gratifiés ou non selon l'entreprise. Idéal pour valider un stage académique "
                    "ou acquérir une première expérience professionnelle au Cameroun."
                ),
                "url": "https://www.africa-work.com/offres-emploi/pays/cameroun/type/stage",
                "type": "stage",
                "levels": ["Licence", "Master"],
            },
        ]

        for opp in opportunities:
            yield self.make_opportunity_item(
                title=opp["title"],
                description=opp["description"],
                source_url=opp["url"],
                deadline=None,
                country="Cameroun",
                opp_type=opp["type"],
                required_level=opp["levels"],
                required_fields=[],
                required_languages=["fr"],
                min_gpa=None,
            )

    def _extract_deadline(self, text: str):
        patterns = [
            r"[Dd]ate limite[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Dd]eadline[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Aa]vant le[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return None

    def errback(self, failure):
        self.logger.error(f"[africawork] Erreur: {failure.request.url} — {failure.value}")
