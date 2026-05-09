# crawler/spiders/scholars4dev.py
# Scholars4Dev — blog de bourses pour étudiants africains et en développement.
# Site: https://scholars4dev.com
# Strategy: scrape article listing pages, follow links, extract key info.

import scrapy
import sys, os, re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class Scholars4DevSpider(BaseOpportunitySpider):
    name = "scholars4dev"
    allowed_domains = ["scholars4dev.com"]

    CATEGORIES = [
        "https://scholars4dev.com/category/scholarships-for-africans/",
        "https://scholars4dev.com/category/scholarships-in-france/",
        "https://scholars4dev.com/category/scholarships-in-germany/",
        "https://scholars4dev.com/category/fellowships/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2.5,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    start_urls = CATEGORIES

    def parse(self, response):
        """Parse a category listing page."""
        # Extract article links from listing
        article_links = response.css("h2.entry-title a::attr(href)").getall()

        if not article_links:
            # Fallback selectors
            article_links = (
                response.css(".post-title a::attr(href)").getall()
                or response.css("article h2 a::attr(href)").getall()
            )

        self.logger.info(f"[scholars4dev] {len(article_links)} articles on {response.url}")

        for link in article_links[:8]:
            yield scrapy.Request(link, callback=self.parse_scholarship)

    def parse_scholarship(self, response):
        """Parse a single scholarship article."""
        title = (
            response.css("h1.entry-title::text").get()
            or response.css("h1::text").get()
            or ""
        ).strip()

        if not title or len(title) < 10:
            return

        # Skip listicle articles (not single scholarships)
        skip_signals = ["top 10", "top 20", "list of", "scholarships in 20", "best scholarship"]
        if any(s in title.lower() for s in skip_signals):
            return

        # Content paragraphs
        paragraphs = response.css(".entry-content p::text").getall()
        description = " ".join(p.strip() for p in paragraphs[:8] if len(p.strip()) > 20)
        if not description:
            description = title

        full_text = " ".join(response.css(".entry-content *::text").getall())

        # Deadline extraction
        deadline = self._extract_deadline(full_text)

        # Country — look in title and content
        country = self._extract_country(title + " " + full_text[:500])

        # Level
        levels = self._extract_levels(title + " " + full_text[:500])

        # Language
        langs = self._extract_languages(full_text[:500])

        # Type — Scholars4Dev = almost always scholarships
        opp_type = "bourse"
        if any(w in title.lower() for w in ["fellowship", "bourse de recherche"]):
            opp_type = "bourse"
        elif any(w in title.lower() for w in ["internship", "stage"]):
            opp_type = "stage"

        yield self.make_opportunity_item(
            title=title[:200],
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
            r"[Cc]losing [Dd]ate[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
            r"[Aa]pply [Bb]y[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
            r"[Dd]ue [Dd]ate[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
            r"[Aa]pplication [Dd]eadline[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return None

    def _extract_country(self, text: str) -> str:
        mapping = {
            "france": "France", "paris": "France",
            "germany": "Allemagne", "deutschland": "Allemagne",
            "usa": "États-Unis", "united states": "États-Unis", "america": "États-Unis",
            "uk": "Royaume-Uni", "united kingdom": "Royaume-Uni",
            "canada": "Canada",
            "australia": "Australie",
            "netherlands": "Pays-Bas",
            "sweden": "Suède",
            "switzerland": "Suisse",
            "japan": "Japon",
            "china": "Chine",
            "south korea": "Corée du Sud",
            "belgium": "Belgique",
            "austria": "Autriche",
            "norway": "Norvège",
        }
        t = text.lower()
        for kw, country in mapping.items():
            if kw in t:
                return country
        return "International"

    def _extract_levels(self, text: str) -> list:
        t = text.lower()
        levels = []
        if any(w in t for w in ["bachelor", "undergraduate", "licence", "bsc", "ba "]):
            levels.append("Licence")
        if any(w in t for w in ["master", "msc", "mba", "postgraduate", "graduate"]):
            levels.append("Master")
        if any(w in t for w in ["phd", "doctoral", "doctorate", "doctorat", "thesis"]):
            levels.append("Doctorat")
        return levels if levels else ["Licence", "Master", "Doctorat"]

    def _extract_languages(self, text: str) -> list:
        t = text.lower()
        langs = []
        if any(w in t for w in ["english", "anglais"]):
            langs.append("en")
        if any(w in t for w in ["french", "français", "francais"]):
            langs.append("fr")
        if any(w in t for w in ["german", "deutsch"]):
            langs.append("de")
        return langs if langs else ["en"]
