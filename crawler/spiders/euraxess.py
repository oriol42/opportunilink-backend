# crawler/spiders/euraxess.py
# EURAXESS — European Commission jobs portal for researchers.
# Has JSON-like listings. Target: jobs open to African applicants.
# URL: https://euraxess.ec.europa.eu/jobs/search

import scrapy
import sys, os, re
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class EuraxessSpider(BaseOpportunitySpider):
    """
    EURAXESS — European researcher mobility portal.
    Targets PhD positions, postdocs, and research fellowships.
    These are HIGH value for Master/Doctorat students.
    """
    name = "euraxess"
    allowed_domains = ["euraxess.ec.europa.eu"]

    start_urls = [
        "https://euraxess.ec.europa.eu/jobs/search?query=africa",
        "https://euraxess.ec.europa.eu/jobs/search?query=cameroon",
        "https://euraxess.ec.europa.eu/jobs/search?query=francophone",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        ),
    }

    def parse(self, response):
        """Parse EURAXESS search results page."""
        self.logger.info(f"[euraxess] Parsing {response.url}")

        # Job listing cards
        job_links = (
            response.css(".job-item a::attr(href)").getall()
            or response.css("article.node--type-job a::attr(href)").getall()
            or response.css("h3 a[href*='/jobs/']::attr(href)").getall()
            or response.css("a[href*='/jobs/']::attr(href)").getall()
        )

        # Filter to actual job pages (not navigation links)
        job_links = [l for l in job_links if "/jobs/" in l and "search" not in l]
        # Remove duplicates
        job_links = list(dict.fromkeys(job_links))

        self.logger.info(f"[euraxess] Found {len(job_links)} job links")

        for link in job_links[:8]:
            yield scrapy.Request(
                response.urljoin(link),
                callback=self.parse_job,
            )

    def parse_job(self, response):
        """Parse a single EURAXESS job posting."""
        title = (
            response.css("h1.page-title::text").get()
            or response.css("h1::text").get()
            or ""
        ).strip()

        if not title or len(title) < 5:
            return

        # Description
        paragraphs = (
            response.css(".field--name-field-job-description p::text").getall()
            or response.css("article p::text").getall()
        )
        description = " ".join(p.strip() for p in paragraphs[:6] if len(p.strip()) > 20)
        if not description:
            description = f"Position de recherche EURAXESS : {title}"

        full_text = " ".join(response.css("*::text").getall())

        # Deadline
        deadline = None
        deadline_el = (
            response.css(".field--name-field-deadline-for-applications::text").get()
            or response.css("time.deadline::attr(datetime)").get()
        )
        if deadline_el:
            deadline = deadline_el.strip()

        # Country — look for institution country
        country = "Europe"
        country_el = response.css(".field--name-field-country::text").get()
        if country_el:
            country = country_el.strip()

        # Level — EURAXESS = research positions = Master/Doctorat
        levels = ["Master", "Doctorat"]
        if "phd" in full_text.lower() or "doctoral" in full_text.lower():
            levels = ["Master", "Doctorat"]
        elif "postdoc" in full_text.lower():
            levels = ["Doctorat"]

        # Language
        langs = []
        if any(w in full_text.lower() for w in ["english", "anglais"]):
            langs.append("en")
        if any(w in full_text.lower() for w in ["french", "français"]):
            langs.append("fr")
        if any(w in full_text.lower() for w in ["german", "deutsch"]):
            langs.append("de")
        if not langs:
            langs = ["en"]

        yield self.make_opportunity_item(
            title=title[:200],
            description=description[:2000],
            source_url=response.url,
            deadline=deadline,
            country=country,
            opp_type="bourse",
            required_level=levels,
            required_fields=[],
            required_languages=langs,
            min_gpa=None,
        )
