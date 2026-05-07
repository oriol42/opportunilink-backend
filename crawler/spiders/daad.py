import scrapy
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class DaadSpider(BaseOpportunitySpider):
    name = "daad"
    allowed_domains = ["daad.de"]

    # Page listing all scholarships for international students
    start_urls = [
        "https://www.daad.de/en/study-and-research-in-germany/scholarships/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,          # Polite — 3s between requests
        "RANDOMIZE_DOWNLOAD_DELAY": True,  # Varies between 1.5s and 4.5s
        "ROBOTSTXT_OBEY": True,
    }

    def parse(self, response):
        """
        Parse the scholarship listing page.
        Try multiple selectors in case DAAD updates their HTML.
        """
        self.logger.info(f"Parsing DAAD listing: {response.url}")

        # Strategy 1: find scholarship cards/articles
        links = (
            response.css("article a::attr(href)").getall()
            or response.css(".scholarship-item a::attr(href)").getall()
            or response.css(".c-scholarshiplist a::attr(href)").getall()
            or response.css("h2 a::attr(href)").getall()
            or response.css("h3 a::attr(href)").getall()
        )

        # Filter: keep only links that look like scholarship detail pages
        scholarship_links = [
            l for l in links
            if l and (
                "scholarship" in l.lower()
                or "stipendium" in l.lower()
                or "/en/find-a-programme/" in l.lower()
                or "/programmes/" in l.lower()
            )
        ]

        # Remove duplicates while keeping order
        seen = set()
        unique_links = []
        for l in scholarship_links:
            if l not in seen:
                seen.add(l)
                unique_links.append(l)

        self.logger.info(f"Found {len(unique_links)} scholarship links")

        # Scrape max 8 to stay polite during dev
        for link in unique_links[:8]:
            yield scrapy.Request(
                response.urljoin(link),
                callback=self.parse_detail,
            )

        # Fallback: if no links found, extract directly from this page
        if not unique_links:
            self.logger.warning("No links found — extracting from listing page directly")
            yield from self._extract_from_listing(response)

    def parse_detail(self, response):
        """
        Parse a single scholarship detail page.
        Multiple fallback selectors for each field.
        """
        # Title — try multiple selectors
        title = (
            response.css("h1.c-headline::text").get()
            or response.css("h1::text").get()
            or response.css("h1 *::text").get()
            or ""
        ).strip()

        if not title or len(title) < 5:
            self.logger.warning(f"No title found at {response.url}, skipping")
            return

        # Description — join first meaningful paragraphs
        paragraphs = (
            response.css(".c-content p::text").getall()
            or response.css("main p::text").getall()
            or response.css("p::text").getall()
        )
        description = " ".join(
            p.strip() for p in paragraphs[:6] if len(p.strip()) > 20
        )
        if not description:
            description = f"DAAD scholarship: {title}. Visit the DAAD website for full details."

        # Deadline — DAAD often shows it in a specific element
        deadline_text = (
            response.css(".c-deadline::text").get()
            or response.css("[class*='deadline']::text").get()
            or response.css("time::attr(datetime)").get()
            or None
        )

        # Determine level from page content
        page_text = response.text.lower()
        required_level = []
        if "bachelor" in page_text or "undergraduate" in page_text or "licence" in page_text:
            required_level.append("Licence")
        if "master" in page_text:
            required_level.append("Master")
        if "phd" in page_text or "doctoral" in page_text or "doctorat" in page_text:
            required_level.append("Doctorat")
        if not required_level:
            required_level = ["Master", "Doctorat"]  # DAAD default

        # Language requirement
        required_languages = []
        if "german" in page_text or "deutsch" in page_text:
            required_languages.append("de")
        if "english" in page_text or "anglais" in page_text:
            required_languages.append("en")
        if not required_languages:
            required_languages = ["en"]

        yield self.make_opportunity_item(
            title=title,
            description=description[:1500],
            source_url=response.url,
            deadline=deadline_text,
            country="Allemagne",
            opp_type="bourse",
            required_level=required_level,
            required_fields=[],  # DAAD is open to all fields generally
            required_languages=required_languages,
            min_gpa=None,
        )

    def _extract_from_listing(self, response):
        """
        Fallback: extract basic info directly from the listing page
        when no detail links are found.
        """
        titles = response.css("h2::text, h3::text").getall()
        for title in titles[:5]:
            title = title.strip()
            if len(title) > 10:
                yield self.make_opportunity_item(
                    title=title,
                    description="Bourse DAAD — Consultez le site officiel pour les détails complets.",
                    source_url=response.url,
                    deadline=None,
                    country="Allemagne",
                    opp_type="bourse",
                    required_level=["Master", "Doctorat"],
                    required_fields=[],
                    required_languages=["en"],
                    min_gpa=None,
                )
