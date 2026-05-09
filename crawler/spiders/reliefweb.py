# crawler/spiders/reliefweb.py
# ReliefWeb public API — jobs & internships from NGOs and UN agencies.
# No API key required. Docs: https://reliefweb.int/help/api
# Strategy: fetch jobs open to Africa/Cameroon, filter by relevance.

import scrapy
import json
import sys, os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class ReliefWebSpider(BaseOpportunitySpider):
    """
    ReliefWeb public REST API.
    Returns structured JSON — no HTML parsing needed.
    Covers: UN, UNICEF, WFP, IRC, MSF, Save the Children, etc.
    """
    name = "reliefweb"

    API_URL = (
        "https://api.reliefweb.int/v1/jobs"
        "?appname=opportunilink"
        "&limit=50"
        "&profile=full"
        "&fields[include][]=title"
        "&fields[include][]=body"
        "&fields[include][]=url"
        "&fields[include][]=date"
        "&fields[include][]=country"
        "&fields[include][]=source"
        "&fields[include][]=experience"
        "&fields[include][]=type"
    )

    # Keywords that signal relevance for students from cameroon
    RELEVANT_KEYWORDS = {
        "intern", "internship", "junior", "graduate", "entry",
        "stagiaire", "junior", "etudiant", "trainee", "associate",
        "africa", "afrique", "cameroon", "cameroun", "francophone",
    }

    custom_settings = {
        "DOWNLOAD_DELAY": 1,
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        yield scrapy.Request(
            url=self.API_URL,
            callback=self.parse_api,
            headers={"Accept": "application/json"},
        )

    def parse_api(self, response):
        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"[reliefweb] JSON parse error: {e}")
            return

        jobs = data.get("data", [])
        self.logger.info(f"[reliefweb] {len(jobs)} jobs fetched")

        kept = 0
        for job in jobs:
            fields = job.get("fields", {})
            title = (fields.get("title") or "").strip()
            if not title:
                continue

            # Filter: keep jobs relevant to students
            title_lower = title.lower()
            body_lower = (fields.get("body") or "")[:500].lower()
            combined = title_lower + " " + body_lower

            if not any(kw in combined for kw in self.RELEVANT_KEYWORDS):
                continue

            kept += 1

            # Description — clean HTML from body
            import re
            body_raw = fields.get("body") or ""
            description = re.sub(r"<[^>]+>", " ", body_raw)
            description = re.sub(r"\s+", " ", description).strip()[:2000]
            if not description:
                description = title

            # Source org
            sources = fields.get("source", [])
            org_name = sources[0].get("name", "") if sources else ""

            # Country
            countries = fields.get("country", [])
            country_str = countries[0].get("name", "International") if countries else "International"
            if any(c.get("name", "").lower() in ["cameroon", "cameroun"] for c in countries):
                country_str = "Cameroun"

            # Deadline — jobs expire after ~30 days if not given
            date_info = fields.get("date", {})
            closing = date_info.get("closing")
            if not closing:
                posting = date_info.get("created")
                if posting:
                    try:
                        dt = datetime.fromisoformat(posting.replace("Z", "+00:00"))
                        closing = (dt + timedelta(days=30)).strftime("%B %d, %Y")
                    except Exception:
                        closing = None

            # Level
            exp = fields.get("experience", [])
            level = self._map_experience(exp)

            source_url = fields.get("url", "") or f"https://reliefweb.int/job/{job.get('id','')}"

            full_title = f"{title} — {org_name}" if org_name else title

            yield self.make_opportunity_item(
                title=full_title[:200],
                description=description,
                source_url=source_url,
                deadline=closing,
                country=country_str,
                opp_type="emploi",
                required_level=level,
                required_fields=[],
                required_languages=self._detect_languages(combined),
                min_gpa=None,
            )

        self.logger.info(f"[reliefweb] {kept}/{len(jobs)} jobs kept after filtering")

    def _map_experience(self, exp_list: list) -> list:
        if not exp_list:
            return ["Licence", "Master"]
        names = [e.get("name", "").lower() for e in exp_list]
        combined = " ".join(names)
        levels = []
        if any(w in combined for w in ["0-2", "0-1", "entry", "junior", "graduate"]):
            levels.extend(["Licence", "Master"])
        if any(w in combined for w in ["3-5", "mid", "intermediate"]):
            levels.append("Master")
        if any(w in combined for w in ["5+", "senior", "expert"]):
            levels.extend(["Master", "Doctorat"])
        return list(set(levels)) if levels else ["Licence", "Master"]

    def _detect_languages(self, text: str) -> list:
        langs = []
        if any(w in text for w in ["english", "anglais"]):
            langs.append("en")
        if any(w in text for w in ["french", "français", "francais", "francophone"]):
            langs.append("fr")
        return langs if langs else ["en"]
