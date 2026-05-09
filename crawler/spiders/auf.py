# crawler/spiders/auf.py
# AUF — Agence Universitaire de la Francophonie
# Bourses, mobilités et postes pour étudiants et chercheurs francophones.
# Site: https://www.auf.org

import scrapy
import sys, os, re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class AufSpider(BaseOpportunitySpider):
    name = "auf"
    allowed_domains = ["auf.org"]

    # Pages d'opportunités AUF
    start_urls = [
        "https://www.auf.org/candidater/",
        "https://www.auf.org/les-actions-de-lauf/appels/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def parse(self, response):
        """Parse listing pages — follow each opportunity link."""
        self.logger.info(f"[auf] Parsing: {response.url}")

        # Multiple selector strategies for AUF's varying layouts
        links = (
            response.css("article.appel a::attr(href)").getall()
            or response.css(".views-row a::attr(href)").getall()
            or response.css("h2.node-title a::attr(href)").getall()
            or response.css("h2 a::attr(href)").getall()
            or response.css("h3 a::attr(href)").getall()
        )

        # Keep only internal AUF links that look like opportunity pages
        filtered = [
            l for l in links
            if l and ("appel" in l.lower() or "candidater" in l.lower()
                      or "bours" in l.lower() or "mobilit" in l.lower()
                      or "/node/" in l)
        ]

        self.logger.info(f"[auf] Found {len(filtered)} opportunity links")

        for link in filtered[:10]:
            yield scrapy.Request(
                response.urljoin(link),
                callback=self.parse_detail,
            )

        # Follow pagination if present
        next_page = (
            response.css("a.pager-next::attr(href)").get()
            or response.css("li.pager__item--next a::attr(href)").get()
        )
        if next_page and "/page/2" not in response.url:
            yield scrapy.Request(response.urljoin(next_page), callback=self.parse)

    def parse_detail(self, response):
        """Parse a single AUF opportunity page."""
        title = (
            response.css("h1.page-header::text").get()
            or response.css("h1.field--name-title::text").get()
            or response.css("h1::text").get()
            or ""
        ).strip()

        if not title or len(title) < 5:
            return

        # Description — multiple content containers
        paragraphs = (
            response.css(".field--name-body p::text").getall()
            or response.css(".node__content p::text").getall()
            or response.css("article p::text").getall()
            or response.css(".content p::text").getall()
        )
        description = " ".join(p.strip() for p in paragraphs[:8] if len(p.strip()) > 20)
        if not description:
            description = f"AUF — {title}. Consultez le site AUF pour les détails complets."

        # Deadline
        full_text = " ".join(response.css("*::text").getall())
        deadline = self._extract_deadline(full_text)

        # Type
        title_lower = title.lower() + description[:200].lower()
        if any(w in title_lower for w in ["bours", "scholarship", "fellowship"]):
            opp_type = "bourse"
        elif any(w in title_lower for w in ["stage", "intern"]):
            opp_type = "stage"
        elif any(w in title_lower for w in ["mobilit", "échange", "exchange"]):
            opp_type = "echange"
        else:
            opp_type = "bourse"  # AUF default

        # Level
        levels = []
        if any(w in title_lower for w in ["master", "msc", "mba", "m2"]):
            levels.append("Master")
        if any(w in title_lower for w in ["doctorat", "phd", "doctoral", "thèse"]):
            levels.append("Doctorat")
        if any(w in title_lower for w in ["licence", "bachelor", "undergraduate", "l3"]):
            levels.append("Licence")
        if not levels:
            levels = ["Licence", "Master", "Doctorat"]

        yield self.make_opportunity_item(
            title=title,
            description=description[:2000],
            source_url=response.url,
            deadline=deadline,
            country="International (Francophonie)",
            opp_type=opp_type,
            required_level=levels,
            required_fields=[],
            required_languages=["fr"],
            min_gpa=None,
        )

    def _extract_deadline(self, text: str):
        patterns = [
            r"[Dd]ate limite[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Dd]eadline[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Cc]l[ôo]ture[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Aa]vant le[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Jj]usqu.au[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Dd]eadline[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return None
