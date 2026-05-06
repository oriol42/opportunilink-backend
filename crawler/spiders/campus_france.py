import scrapy
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class CampusFranceSpider(BaseOpportunitySpider):
    name = "campus_france"
    allowed_domains = ["cm.campusfrance.org"]
    start_urls = ["https://www.cm.campusfrance.org/fr/bourses"]

    def parse(self, response):
        bourse_links = response.css("a::attr(href)").getall()
        bourse_links = [l for l in bourse_links if "bourse" in l.lower()]

        self.logger.info(f"Trouve {len(bourse_links)} liens bourses")

        for link in bourse_links[:5]:
            yield scrapy.Request(response.urljoin(link), callback=self.parse_bourse)

        if not bourse_links:
            yield from self.parse_bourse(response)

    def parse_bourse(self, response):
        title = response.css("h1::text, h1 *::text").get(default="").strip()
        if not title or len(title) < 5:
            return

        paragraphs = response.css("p::text").getall()
        description = " ".join(p.strip() for p in paragraphs if p.strip())
        if not description:
            description = "Bourse Campus France pour etudiants camerounais."

        yield self.make_opportunity_item(
            title=title,
            description=description[:1000],
            source_url=response.url,
            deadline=None,
            country="France",
            opp_type="bourse",
            required_level=["Licence", "Master", "Doctorat"],
            required_fields=[],
            required_languages=["fr"],
            min_gpa=None,
        )
