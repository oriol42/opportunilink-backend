# crawler/spiders/mtn_cm.py
# MTN Cameroun careers page — local jobs in Cameroon.
# Focuses on tech and business roles relevant to students.

import scrapy
import sys, os, re
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class MtnCmSpider(BaseOpportunitySpider):
    name = "mtn_cm"
    allowed_domains = ["mtn.cm", "mtn.com"]

    start_urls = [
        "https://www.mtn.cm/fr/particuliers/mtn-group/carrieres/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        """Parse MTN careers page."""
        self.logger.info(f"[mtn_cm] Parsing {response.url}")

        # Try multiple selectors for job links
        job_links = (
            response.css(".job-listing a::attr(href)").getall()
            or response.css(".career-item a::attr(href)").getall()
            or response.css("article.job a::attr(href)").getall()
            or response.css("a[href*='career']::attr(href)").getall()
            or response.css("a[href*='job']::attr(href)").getall()
        )

        if job_links:
            for link in job_links[:10]:
                yield scrapy.Request(response.urljoin(link), callback=self.parse_job)
        else:
            # No individual links found — extract directly from listing
            self.logger.info("[mtn_cm] No job links found — extracting from page directly")
            yield from self._extract_from_page(response)

    def parse_job(self, response):
        title = (response.css("h1::text").get() or "").strip()
        if not title or len(title) < 5:
            yield from self._extract_from_page(response)
            return

        paragraphs = response.css("p::text").getall()
        description = " ".join(p.strip() for p in paragraphs[:6] if len(p.strip()) > 20)
        if not description:
            description = f"Offre d'emploi MTN Cameroun : {title}."

        yield self.make_opportunity_item(
            title=title,
            description=description[:2000],
            source_url=response.url,
            deadline=None,
            country="Cameroun",
            opp_type="emploi",
            required_level=["Licence", "Master", "Ingénieur"],
            required_fields=["Informatique", "Télécommunications", "Gestion", "Économie"],
            required_languages=["fr", "en"],
            min_gpa=None,
        )

    def _extract_from_page(self, response):
        """Fallback: create a generic MTN careers opportunity."""
        titles = response.css("h2::text, h3::text, .job-title::text").getall()
        for title in titles[:5]:
            title = title.strip()
            if len(title) > 10 and not any(w in title.lower() for w in ["menu", "navigation", "footer"]):
                yield self.make_opportunity_item(
                    title=f"MTN Cameroun — {title}",
                    description="Opportunité d'emploi chez MTN Cameroun, leader des télécommunications. Consultez la page carrières officielle pour les détails et postuler.",
                    source_url=response.url,
                    deadline=None,
                    country="Cameroun",
                    opp_type="emploi",
                    required_level=["Licence", "Master", "Ingénieur"],
                    required_fields=["Informatique", "Télécommunications", "Gestion"],
                    required_languages=["fr", "en"],
                    min_gpa=None,
                )
