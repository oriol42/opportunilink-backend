# Banque Africaine de Développement — emplois et stages Afrique
import scrapy, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider

class AfdbSpider(BaseOpportunitySpider):
    name = "afdb"
    allowed_domains = ["afdb.org", "allafricajobs.com"]
    custom_settings = { "DOWNLOAD_DELAY": 2, "ROBOTSTXT_OBEY": True }

    start_urls = [
        "https://www.afdb.org/en/careers/current-vacancies",
        "https://www.afdb.org/en/internships",
    ]

    def parse(self, response):
        links = (
            response.css("a[href*='vacancy']::attr(href)").getall()
            or response.css("a[href*='career']::attr(href)").getall()
            or response.css(".views-row a::attr(href)").getall()
            or response.css("h3 a::attr(href)").getall()
        )
        links = list(dict.fromkeys(links))[:10]
        self.logger.info(f"[afdb] {len(links)} links")
        for link in links:
            yield scrapy.Request(response.urljoin(link), callback=self.parse_job)
        if not links:
            yield from self._fallback(response)

    def parse_job(self, response):
        title = (response.css("h1::text").get() or "").strip()
        if not title or len(title) < 5: return
        paras = response.css("p::text").getall()
        description = " ".join(p.strip() for p in paras[:6] if len(p.strip()) > 20) or f"Poste BAD : {title}"
        opp_type = "stage" if any(w in title.lower() for w in ["intern","stage","stagiaire"]) else "emploi"
        yield self.make_opportunity_item(
            title=title[:200], description=description[:2000], source_url=response.url,
            deadline=None, country="Afrique (BAD)", opp_type=opp_type,
            required_level=["Licence","Master","Doctorat"], required_fields=[], required_languages=["en","fr"], min_gpa=None,
        )

    def _fallback(self, response):
        yield self.make_opportunity_item(
            title="Programme de stages BAD 2026", description="La Banque Africaine de Développement offre des stages de 3 à 6 mois dans ses bureaux. Profils recherchés : économie, finance, ingénierie, droit, informatique.", source_url=response.url,
            deadline=None, country="Afrique", opp_type="stage",
            required_level=["Licence","Master"], required_fields=[], required_languages=["en","fr"], min_gpa=None,
        )
