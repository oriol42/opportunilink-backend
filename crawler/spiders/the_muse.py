# crawler/spiders/the_muse.py
# The Muse public API — no API key, no registration needed.
# NOTE: category filter is no longer supported by the API.
# Strategy: fetch pages without filter, keep only relevant jobs by keyword matching.

import scrapy
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class TheMuseSpider(BaseOpportunitySpider):
    """
    The Muse public jobs API.
    Fetches entry + mid level jobs from the public feed.
    Filters in-spider by keyword relevance to avoid storing nursing/trades jobs.
    """
    name = "the_muse"

    # How many pages to fetch — each page = 20 jobs
    # 5 pages = 100 raw jobs → ~30-40 relevant after keyword filtering
    PAGES = 5

    # Keywords that signal a job relevant for Cameroonian students
    RELEVANT_KEYWORDS = {
        "software", "developer", "engineer", "data", "analyst",
        "finance", "marketing", "project manager", "product",
        "business", "accountant", "designer", "it ", "network",
        "operations", "consultant", "research", "communication",
        "python", "java", "javascript", "sql", "cloud",
    }

    # Keywords that signal an irrelevant job — skip immediately
    SKIP_KEYWORDS = {
        "nurse", "nursing", "lpn", "rn ", "caregiver", "cdl",
        "truck", "driver", "plumber", "electrician", "hvac",
        "dental", "physician", "therapist", "warehouse",
    }

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "ROBOTSTXT_OBEY": False,
        "CONCURRENT_REQUESTS": 2,
    }

    def start_requests(self):
        for page in range(1, self.PAGES + 1):
            # level=entry + level=mid targets fresh graduates and junior profiles
            url = (
                f"https://www.themuse.com/api/public/jobs"
                f"?level=entry&level=mid&page={page}"
            )
            yield scrapy.Request(
                url=url,
                callback=self.parse_jobs,
                meta={"page": page},
            )

    def parse_jobs(self, response):
        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"Failed to parse The Muse JSON: {e}")
            return

        results = data.get("results", [])
        page = response.meta["page"]
        kept = 0

        for job in results:
            title = (job.get("name") or "").strip()
            if not title:
                continue

            title_lower = title.lower()

            # Skip irrelevant sectors immediately
            if any(kw in title_lower for kw in self.SKIP_KEYWORDS):
                continue

            # Keep only jobs that match at least one relevant keyword
            if not any(kw in title_lower for kw in self.RELEVANT_KEYWORDS):
                continue

            kept += 1
            company_name = job.get("company", {}).get("name", "Unknown company")

            # Use HTML content field for richer description
            raw_contents = job.get("contents", "") or ""
            # Strip HTML tags simply — pipeline can handle plain text
            import re
            clean_description = re.sub(r"<[^>]+>", " ", raw_contents).strip()
            clean_description = re.sub(r"\s+", " ", clean_description)

            if not clean_description:
                clean_description = f"{title} at {company_name}."

            source_url = job.get("refs", {}).get("landing_page", "")
            country = self._map_location(job.get("locations", []))
            deadline = self._estimate_deadline(job.get("publication_date"))
            required_level = self._map_muse_levels(job.get("levels", []))

            yield self.make_opportunity_item(
                title=title,
                description=clean_description[:2000],
                source_url=source_url,
                deadline=deadline,
                country=country,
                opp_type="emploi",
                required_level=required_level,
                required_fields=[],
                required_languages=["en"],
                min_gpa=None,
            )

        self.logger.info(
            f"[the_muse] page {page} → {len(results)} fetched, {kept} relevant kept"
        )

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _map_location(self, locations: list) -> str:
        if not locations:
            return "International"

        names = [loc.get("name", "").lower() for loc in locations]

        if any("remote" in n for n in names):
            return "Remote (International)"

        africa_keywords = {
            "nigeria": "Nigeria",
            "south africa": "Afrique du Sud",
            "kenya": "Kenya",
            "ghana": "Ghana",
            "cameroon": "Cameroun",
        }
        for name in names:
            for keyword, country in africa_keywords.items():
                if keyword in name:
                    return country

        first = locations[0].get("name", "International")
        return first or "International"

    def _map_muse_levels(self, levels: list) -> list:
        level_map = {
            "entry": ["Licence", "Master"],
            "mid": ["Master"],
            "senior": ["Master", "Doctorat"],
            "manager": ["Master", "Doctorat"],
        }
        result = set()
        for level in levels:
            short = level.get("short_name", "entry")
            result.update(level_map.get(short, ["Licence", "Master"]))
        return list(result) if result else ["Licence", "Master"]

    def _estimate_deadline(self, pub_date_str: str | None) -> str | None:
        if not pub_date_str:
            return None
        try:
            dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
            return (dt + timedelta(days=30)).strftime("%B %d, %Y")
        except Exception:
            return None
