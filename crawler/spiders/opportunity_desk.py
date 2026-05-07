import scrapy
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class OpportunityDeskSpider(BaseOpportunitySpider):
    """
    Spider for OpportunityDesk.org — the #1 platform for African youth opportunities.
    Covers: scholarships, internships, competitions, fellowships, jobs, training.
    """
    name = "opportunity_desk"
    allowed_domains = ["opportunitydesk.org"]

    # Each category maps to one of our internal opportunity types
    CATEGORY_MAP = {
        "fellowships-and-scholarships": "bourse",
        "internships":                  "stage",
        "competitions":                 "concours",
        "jobs":                         "emploi",
        "training-and-courses":         "formation",
        "exchange-programs":            "echange",
    }

    start_urls = [
        f"https://opportunitydesk.org/category/{cat}/"
        for cat in CATEGORY_MAP.keys()
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def parse(self, response):
        """Parse a category listing page and follow each article link."""

        # Detect which category we're on from the URL
        opp_type = "bourse"  # default
        for cat_slug, cat_type in self.CATEGORY_MAP.items():
            if cat_slug in response.url:
                opp_type = cat_type
                break

        # Select all article cards on the page
        articles = response.css("article.l-post")
        self.logger.info(
            f"[{opp_type}] Found {len(articles)} articles on {response.url}"
        )

        for article in articles:
            link = article.css("h2.is-title a::attr(href)").get()
            title = article.css("h2.is-title a::text").get(default="").strip()
            pub_date = article.css("time.post-date::attr(datetime)").get()

            if not link or not title:
                continue

            # Pass data to the detail parser via meta
            yield scrapy.Request(
                url=link,
                callback=self.parse_detail,
                meta={
                    "opp_type": opp_type,
                    "pub_date": pub_date,
                    "title_from_listing": title,
                },
            )

        # Follow pagination — "Next page" link
        next_page = response.css("a.next.page-numbers::attr(href)").get()
        if next_page:
            # Limit to first 3 pages per category during dev
            current_page = int(response.url.split("/page/")[-1].rstrip("/")) if "/page/" in response.url else 1
            if current_page < 3:
                yield scrapy.Request(next_page, callback=self.parse)

    def parse_detail(self, response):
        """Parse a single opportunity detail page."""

        opp_type = response.meta["opp_type"]
        pub_date = response.meta["pub_date"]
        fallback_title = response.meta["title_from_listing"]

        # Title — prefer h1 on the page
        title = (
            response.css("h1.post-title::text").get()
            or response.css("h1.entry-title::text").get()
            or response.css("h1::text").get()
            or fallback_title
        ).strip()

        if not title or len(title) < 5:
            return

        # Full article content
        paragraphs = (
            response.css("div.post-content p::text").getall()
            or response.css("div.entry-content p::text").getall()
            or response.css("article p::text").getall()
        )
        description = " ".join(
            p.strip() for p in paragraphs[:8] if len(p.strip()) > 20
        )
        if not description:
            description = title

        # Deadline — look for keywords in full page text
        deadline = self._extract_deadline(response)

        # Country — look for country mentions in title/description
        country = self._extract_country(title + " " + description)

        # Required level — infer from title/description
        required_level = self._extract_level(title + " " + description)

        # Required languages
        required_languages = self._extract_languages(title + " " + description)

        yield self.make_opportunity_item(
            title=title,
            description=description[:2000],
            source_url=response.url,
            deadline=deadline,
            country=country,
            opp_type=opp_type,
            required_level=required_level,
            required_fields=[],
            required_languages=required_languages,
            min_gpa=None,
        )

    def _extract_deadline(self, response):
        """Try to find a deadline date in the page content."""
        page_text = response.css("div.post-content *::text, div.entry-content *::text").getall()
        full_text = " ".join(page_text)

        # Look for patterns like "Deadline: May 30, 2026" or "closes on June 1"
        import re
        patterns = [
            r"[Dd]eadline[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
            r"[Cc]loses?[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
            r"[Aa]pply by[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
            r"[Dd]ue [Dd]ate[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
        ]
        for pattern in patterns:
            match = re.search(pattern, full_text)
            if match:
                return match.group(1)
        return None

    def _extract_country(self, text):
        """Detect destination country from text."""
        country_map = {
            "USA": "États-Unis", "United States": "États-Unis", "America": "États-Unis",
            "UK": "Royaume-Uni", "United Kingdom": "Royaume-Uni", "Britain": "Royaume-Uni",
            "Germany": "Allemagne", "Deutschland": "Allemagne",
            "France": "France",
            "Canada": "Canada",
            "Australia": "Australie",
            "Netherlands": "Pays-Bas", "Holland": "Pays-Bas",
            "Sweden": "Suède",
            "Norway": "Norvège",
            "China": "Chine",
            "Japan": "Japon",
            "South Africa": "Afrique du Sud",
            "Nigeria": "Nigeria",
            "Cameroon": "Cameroun",
        }
        for keyword, country in country_map.items():
            if keyword.lower() in text.lower():
                return country
        return "International"

    def _extract_level(self, text):
        """Infer required academic level from text."""
        text_lower = text.lower()
        levels = []
        if any(w in text_lower for w in ["bachelor", "undergraduate", "licence", "bsc", "ba "]):
            levels.append("Licence")
        if any(w in text_lower for w in ["master", "postgraduate", "msc", "mba", "graduate"]):
            levels.append("Master")
        if any(w in text_lower for w in ["phd", "doctoral", "doctorate", "doctorat"]):
            levels.append("Doctorat")
        return levels if levels else ["Licence", "Master", "Doctorat"]

    def _extract_languages(self, text):
        """Detect language requirements from text."""
        text_lower = text.lower()
        langs = []
        if any(w in text_lower for w in ["english", "anglais"]):
            langs.append("en")
        if any(w in text_lower for w in ["french", "français", "francais"]):
            langs.append("fr")
        if any(w in text_lower for w in ["german", "deutsch", "allemand"]):
            langs.append("de")
        return langs if langs else ["en"]
