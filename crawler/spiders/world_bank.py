# World Bank Jobs — emplois et stages ONU/Banque Mondiale
import scrapy, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider

class WorldBankSpider(BaseOpportunitySpider):
    name = "world_bank"
    custom_settings = { "DOWNLOAD_DELAY": 2, "ROBOTSTXT_OBEY": True }

    API_URL = "https://api.worldbank.org/v2/jobs?format=json&per_page=50"

    def start_requests(self):
        urls = [
            "https://jobs.worldbank.org/en/jobs/all-jobs?term=africa&country=CM",
            "https://jobs.worldbank.org/en/jobs/all-jobs?term=cameroon",
            "https://jobs.worldbank.org/en/jobs/all-jobs?term=intern",
        ]
        for url in urls:
            yield scrapy.Request(url, callback=self.parse, headers={"Accept": "text/html"})

    def parse(self, response):
        links = response.css("a.job-link::attr(href)").getall() or response.css("h3 a::attr(href)").getall() or response.css("a[href*='/jobs/']::attr(href)").getall()
        links = list(dict.fromkeys([l for l in links if "/jobs/" in l and "all-jobs" not in l]))
        self.logger.info(f"[world_bank] {len(links)} jobs found")
        for link in links[:10]:
            yield scrapy.Request(response.urljoin(link), callback=self.parse_job)

    def parse_job(self, response):
        title = (response.css("h1::text").get() or "").strip()
        if not title or len(title) < 5: return
        paras = response.css(".job-description p::text, .field-items p::text, article p::text").getall()
        description = " ".join(p.strip() for p in paras[:6] if len(p.strip()) > 20)
        if not description: description = f"Poste Banque Mondiale : {title}"
        full = response.text.lower()
        levels = []
        if any(w in full for w in ["bachelor","licence","undergraduate"]): levels.append("Licence")
        if any(w in full for w in ["master","msc","graduate"]): levels.append("Master")
        if any(w in full for w in ["phd","doctoral"]): levels.append("Doctorat")
        if not levels: levels = ["Master","Doctorat"]
        yield self.make_opportunity_item(
            title=title[:200], description=description[:2000], source_url=response.url,
            deadline=None, country="International", opp_type="emploi",
            required_level=levels, required_fields=[], required_languages=["en"], min_gpa=None,
        )
