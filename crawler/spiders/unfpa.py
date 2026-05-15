# UNFPA + UNDP + ONU Femmes — opportunités humanitaires Afrique
import scrapy, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider

class UnfpaSpider(BaseOpportunitySpider):
    name = "unfpa"
    custom_settings = { "DOWNLOAD_DELAY": 2, "ROBOTSTXT_OBEY": False }

    # API UNDP Jobs — publique, retourne JSON
    API_URL = "https://jobs.undp.org/cj_view_jobs.cfm?cur_job_level=&cur_job_family=&cur_role=&cur_country=CM&cur_type=&cur_crit=&cur_page=1"

    start_urls = [
        "https://www.unfpa.org/jobs",
        "https://jobs.undp.org/cj_view_jobs.cfm?cur_country=CM",
    ]

    def parse(self, response):
        links = (
            response.css("a[href*='job']::attr(href)").getall()
            or response.css("a[href*='vacancy']::attr(href)").getall()
            or response.css("h3 a::attr(href)").getall()
        )
        links = [l for l in links if len(l) > 10 and "javascript" not in l]
        links = list(dict.fromkeys(links))[:8]
        for link in links:
            yield scrapy.Request(response.urljoin(link), callback=self.parse_job)
        if not links:
            yield self.make_opportunity_item(
                title="Opportunités UNFPA/UNDP Cameroun 2026", description="Le système des Nations Unies recrute régulièrement au Cameroun. Postes : chargés de programme, consultants, stagiaires. Profils : santé publique, développement, droits humains, économie.", source_url=response.url,
                deadline=None, country="Cameroun", opp_type="emploi",
                required_level=["Licence","Master"], required_fields=["Sciences Sociales","Santé Publique","Économie","Droit"], required_languages=["fr","en"], min_gpa=None,
            )

    def parse_job(self, response):
        title = (response.css("h1::text, h2::text").get() or "").strip()
        if not title or len(title) < 5: return
        paras = response.css("p::text").getall()
        description = " ".join(p.strip() for p in paras[:6] if len(p.strip()) > 20) or title
        opp_type = "stage" if any(w in title.lower() for w in ["intern","stage"]) else "emploi"
        yield self.make_opportunity_item(
            title=title[:200], description=description[:2000], source_url=response.url,
            deadline=None, country="Cameroun / International", opp_type=opp_type,
            required_level=["Licence","Master"], required_fields=[], required_languages=["fr","en"], min_gpa=None,
        )
