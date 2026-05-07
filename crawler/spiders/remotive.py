import scrapy
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class RemotiveSpider(BaseOpportunitySpider):
    """
    Spider for Remotive.com API — remote tech jobs accessible from Cameroon.
    Uses their public JSON API (no scraping, official endpoint).
    Categories: software-dev, data, devops, design, product, marketing.
    """
    name = "remotive"

    # Remotive's public API endpoint — returns JSON directly
    API_URL = "https://remotive.com/api/remote-jobs?limit=50&category={category}"

    CATEGORY_MAP = {
        "software-dev":         "emploi",
        "data":                 "emploi",
        "devops-sysadmin":      "emploi",
        "product":              "emploi",
        "design":               "emploi",
        "writing":              "emploi",
    }

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "ROBOTSTXT_OBEY": False,  # API endpoint, not a web page
    }

    def start_requests(self):
        for category in self.CATEGORY_MAP:
            yield scrapy.Request(
                url=self.API_URL.format(category=category),
                callback=self.parse_api,
                meta={"category": category},
            )

    def parse_api(self, response):
        """Parse JSON API response from Remotive."""
        category = response.meta["category"]
        opp_type = self.CATEGORY_MAP[category]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON for category {category}")
            return

        jobs = data.get("jobs", [])
        self.logger.info(f"[remotive/{category}] Found {len(jobs)} jobs")

        for job in jobs:
            title = job.get("title", "").strip()
            if not title:
                continue

            # Clean HTML tags from description
            description = self._clean_html(job.get("description", ""))[:2000]

            # Publication date as deadline proxy (remote jobs rarely have deadlines)
            pub_date = job.get("publication_date", "")

            yield self.make_opportunity_item(
                title=title,
                description=description or f"Remote job: {title}",
                source_url=job.get("url", ""),
                deadline=None,
                country="Remote (International)",
                opp_type=opp_type,
                required_level=["Licence", "Master"],
                required_fields=self._map_field(category),
                required_languages=["en"],
                min_gpa=None,
            )

    def _clean_html(self, html_text):
        """Remove HTML tags from a string."""
        import re
        clean = re.sub(r"<[^>]+>", " ", html_text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def _map_field(self, category):
        """Map Remotive category to academic fields."""
        field_map = {
            "software-dev":    ["Informatique", "Génie Logiciel"],
            "data":            ["Informatique", "Mathématiques", "Statistiques"],
            "devops-sysadmin": ["Informatique", "Réseaux"],
            "product":         ["Informatique", "Management"],
            "design":          ["Informatique", "Design"],
            "writing":         [],
        }
        return field_map.get(category, [])
