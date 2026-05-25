# crawler/spiders/jobnetafrica.py
# JobnetAfrica — Plateforme d'emplois et stages dédiée à l'Afrique.
# Très utilisée pour les profils qualifiés africains.
# Site: https://jobnetafrica.com

import scrapy
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class JobnetAfricaSpider(BaseOpportunitySpider):
    name = "jobnetafrica"
    allowed_domains = ["jobnetafrica.com"]

    start_urls = [
        "https://jobnetafrica.com/jobs/?country=cameroon",
        "https://jobnetafrica.com/jobs/?type=internship",
        "https://jobnetafrica.com/jobs/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        self.logger.info(f"[jobnetafrica] Parsing: {response.url}")

        links = (
            response.css(".job-title a::attr(href)").getall()
            or response.css(".job_listing h3 a::attr(href)").getall()
            or response.css("h2.entry-title a::attr(href)").getall()
            or response.css("article h2 a::attr(href)").getall()
            or response.css("a.job-title::attr(href)").getall()
        )

        self.logger.info(f"[jobnetafrica] {len(links)} offres trouvées")

        for link in links[:10]:
            yield scrapy.Request(
                response.urljoin(link),
                callback=self.parse_detail,
                errback=self.errback,
            )

        # Pagination
        next_page = (
            response.css("a.next::attr(href)").get()
            or response.css(".next-page a::attr(href)").get()
        )
        current_page = int(re.search(r"page=(\d+)", response.url).group(1)) if "page=" in response.url else 1
        if next_page and current_page < 2:
            yield scrapy.Request(next_page, callback=self.parse)

    def parse_detail(self, response):
        title = (
            response.css("h1.job_title::text").get()
            or response.css("h1.entry-title::text").get()
            or response.css("h1::text").get()
            or ""
        ).strip()

        if not title or len(title) < 5:
            return

        paragraphs = (
            response.css(".job-description p::text").getall()
            or response.css(".entry-content p::text").getall()
            or response.css("p::text").getall()
        )
        description = " ".join(
            p.strip() for p in paragraphs[:8] if len(p.strip()) > 20
        )
        if not description:
            description = (
                f"JobnetAfrica — {title}. "
                "Opportunité professionnelle en Afrique. "
                "Consultez le site JobnetAfrica pour postuler."
            )

        full_text = " ".join(response.css("*::text").getall())
        deadline = self._extract_deadline(full_text)
        text_lower = (title + " " + description[:300]).lower()

        # Type
        if any(w in text_lower for w in ["intern", "stage", "trainee"]):
            opp_type = "stage"
        elif any(w in text_lower for w in ["volunteer", "bénévol"]):
            opp_type = "bourse"
        else:
            opp_type = "emploi"

        # Niveau
        levels = []
        if any(w in text_lower for w in ["bachelor", "licence", "undergraduate", "degree"]):
            levels.append("Licence")
        if any(w in text_lower for w in ["master", "msc", "postgraduate"]):
            levels.append("Master")
        if not levels:
            levels = ["Licence", "Master"]

        # Pays
        country = "International (Afrique)"
        if "cameroon" in text_lower or "cameroun" in text_lower or "yaound" in text_lower or "douala" in text_lower:
            country = "Cameroun"

        yield self.make_opportunity_item(
            title=title,
            description=description[:2000],
            source_url=response.url,
            deadline=deadline,
            country=country,
            opp_type=opp_type,
            required_level=levels,
            required_fields=[],
            required_languages=["en", "fr"],
            min_gpa=None,
        )

    def _extract_deadline(self, text: str):
        patterns = [
            r"[Dd]eadline[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Aa]pply by[:\s]+([A-Z][a-z]+ \d{1,2},? \d{4})",
            r"[Cc]losing [Dd]ate[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return None

    def errback(self, failure):
        self.logger.error(f"[jobnetafrica] Erreur: {failure.request.url} — {failure.value}")
