# crawler/spiders/scholars4dev_cm.py
# Scholars4Dev — Agrégateur mondial de bourses très populaire en Afrique.
# Site: https://www.scholars4dev.com

import scrapy
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class Scholars4DevCmSpider(BaseOpportunitySpider):
    name = "scholars4dev_cm"
    allowed_domains = ["scholars4dev.com"]

    start_urls = [
        "https://www.scholars4dev.com/",
        "https://www.scholars4dev.com/category/scholarships-list/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def parse(self, response):
        self.logger.info(f"[scholars4dev] Parsing: {response.url}")

        # Articles = liens avec un numéro dans l'URL (pattern WordPress /1234/titre/)
        links = response.css("a::attr(href)").getall()
        article_links = [
            l for l in links
            if l and re.search(r"scholars4dev\.com/\d+/", l)
        ]

        # Dédoublonnage
        seen = set()
        unique = []
        for l in article_links:
            if l not in seen:
                seen.add(l)
                unique.append(l)

        self.logger.info(f"[scholars4dev] {len(unique)} articles trouvés")

        for link in unique[:12]:
            yield scrapy.Request(
                link,
                callback=self.parse_detail,
                errback=self.errback,
            )

        # Pagination — max 2 pages
        next_page = response.css("a.next.page-numbers::attr(href)").get()
        current_page = int(re.search(r"/page/(\d+)", response.url).group(1)) if "/page/" in response.url else 1
        if next_page and current_page < 2:
            yield scrapy.Request(next_page, callback=self.parse)

    def parse_detail(self, response):
        title = (
            response.css("h1.entry-title::text").get()
            or response.css("h1::text").get()
            or ""
        ).strip()

        if not title or len(title) < 5:
            return

        paragraphs = (
            response.css(".entry-content p::text").getall()
            or response.css("article p::text").getall()
        )
        description = " ".join(
            p.strip() for p in paragraphs[:8] if len(p.strip()) > 20
        )
        if not description:
            description = f"Bourse internationale — {title}. Visitez le site pour les détails."

        full_text = " ".join(response.css("*::text").getall())
        deadline = self._extract_deadline(full_text)
        text_lower = (title + " " + description[:300]).lower()

        # Type
        if any(w in text_lower for w in ["internship", "stage", "intern"]):
            opp_type = "stage"
        elif any(w in text_lower for w in ["exchange", "échange"]):
            opp_type = "echange"
        else:
            opp_type = "bourse"

        # Niveau
        levels = []
        if any(w in text_lower for w in ["undergraduate", "bachelor", "licence"]):
            levels.append("Licence")
        if any(w in text_lower for w in ["master", "msc", "mba", "postgraduate"]):
            levels.append("Master")
        if any(w in text_lower for w in ["phd", "doctoral", "doctorate"]):
            levels.append("Doctorat")
        if not levels:
            levels = ["Licence", "Master", "Doctorat"]

        # Pays
        country_map = {
            "usa": "États-Unis", "united states": "États-Unis",
            "uk": "Royaume-Uni", "united kingdom": "Royaume-Uni",
            "canada": "Canada", "france": "France",
            "germany": "Allemagne", "australia": "Australie",
            "china": "Chine", "japan": "Japon",
            "netherlands": "Pays-Bas", "belgium": "Belgique",
            "sweden": "Suède", "norway": "Norvège", "switzerland": "Suisse",
        }
        country = "International"
        for keyword, country_name in country_map.items():
            if keyword in text_lower:
                country = country_name
                break

        langs = []
        if any(w in text_lower for w in ["english", "anglais"]):
            langs.append("en")
        if any(w in text_lower for w in ["french", "français"]):
            langs.append("fr")
        if not langs:
            langs = ["en"]

        yield self.make_opportunity_item(
            title=title,
            description=description[:2000],
            source_url=response.url,
            deadline=deadline,
            country=country,
            opp_type=opp_type,
            required_level=levels,
            required_fields=[],
            required_languages=langs,
            min_gpa=None,
        )

    def _extract_deadline(self, text: str):
        patterns = [
            r"[Dd]eadline[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
            r"[Dd]eadline[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Aa]pply (?:by|before)[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
            r"[Cc]losing [Dd]ate[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return None

    def errback(self, failure):
        self.logger.error(f"[scholars4dev] Erreur: {failure.request.url} — {failure.value}")
