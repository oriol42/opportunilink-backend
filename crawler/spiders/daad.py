import scrapy
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class DaadSpider(BaseOpportunitySpider):
    name = "daad"
    allowed_domains = ["daad.de"]
    start_urls = ["https://www.daad.de/en/study-and-research-in-germany/scholarships/"]

    def parse(self, response):
        links = response.css("a::attr(href)").getall()
        scholarship_links = [l for l in links if "scholarship" in l.lower() or "burs" in l.lower()]

        self.logger.info(f"Trouve {len(scholarship_links)} liens")

        for link in scholarship_links[:5]:
            yield scrapy.Request(response.urljoin(link), callback=self.parse_detail)

    def parse_detail(self, response):
        title = response.css("h1::text, h1 *::text").get(default="").strip()
        if not title or len(title) < 5:
            return

        paragraphs = response.css("p::text").getall()
        description = " ".join(p.strip() for p in paragraphs[:5] if p.strip())

        yield self.make_opportunity_item(
            title=title,
            description=description[:1000] or "Bourse DAAD Allemagne.",
            source_url=response.url,
            deadline=None,
            country="Allemagne",
            opp_type="bourse",
            required_level=["Licence", "Master", "Doctorat"],
            required_fields=[],
            required_languages=["en"],
            min_gpa=None,
        )
