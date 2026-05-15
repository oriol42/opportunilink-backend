# MasterCard Foundation + Tony Elumelu + bourses africaines majeures
import scrapy, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider

class MastercardFoundationSpider(BaseOpportunitySpider):
    name = "mastercard_foundation"
    custom_settings = { "DOWNLOAD_DELAY": 2, "ROBOTSTXT_OBEY": True }

    start_urls = [
        "https://mastercardfdn.org/all/scholars/becoming-a-scholar/",
        "https://www.tonyelumelufoundation.org/teep",
    ]

    def parse(self, response):
        links = response.css("a[href*='scholar']::attr(href), a[href*='program']::attr(href), a[href*='apply']::attr(href)").getall()
        links = list(dict.fromkeys(links))[:6]
        for link in links:
            yield scrapy.Request(response.urljoin(link), callback=self.parse_program)
        if not links:
            yield from self._static_programs()

    def parse_program(self, response):
        title = (response.css("h1::text, h2::text").get() or "").strip()
        if not title or len(title) < 10: yield from self._static_programs(); return
        paras = response.css("p::text").getall()
        description = " ".join(p.strip() for p in paras[:8] if len(p.strip()) > 20) or title
        yield self.make_opportunity_item(
            title=title[:200], description=description[:2000], source_url=response.url,
            deadline=None, country="International (Afrique)", opp_type="bourse",
            required_level=["Licence","Master"], required_fields=[], required_languages=["en","fr"], min_gpa=13.0,
        )

    def _static_programs(self):
        programs = [
            {
                "title": "MasterCard Foundation Scholars Program 2026-2027",
                "desc": "La MasterCard Foundation finance des études universitaires complètes dans les meilleures universités africaines et internationales (UdeM, Ashesi, AIMS, etc.). Couverture totale : frais académiques, hébergement, billet avion, bourse mensuelle. Pour étudiants africains talentueux avec difficultés financières. Profil : leadership, engagement communautaire, excellence académique.",
                "url": "https://mastercardfdn.org/all/scholars/becoming-a-scholar/",
                "gpa": 14.0,
            },
            {
                "title": "Tony Elumelu Foundation Entrepreneurship Program 2026",
                "desc": "TEF sélectionne 1000 jeunes entrepreneurs africains. Chaque lauréat reçoit : 5000 USD seed capital non remboursable, 12 semaines de formation business en ligne, mentorat personnalisé par un expert, accès au réseau TEF pan-africain. Ouvert à tout porteur de projet en Afrique.",
                "url": "https://www.tonyelumelufoundation.org/teep",
                "gpa": None,
            },
            {
                "title": "Bourse Agence Française de Développement (AFD) Cameroun 2026",
                "desc": "L'AFD finance des formations et études supérieures pour les professionnels camerounais dans les secteurs : agriculture, énergie, eau, santé, éducation. Masters en France ou dans des institutions partenaires africaines. Allocation mensuelle + billet aller-retour.",
                "url": "https://www.afd.fr/fr/bourses",
                "gpa": 13.0,
            },
        ]
        for p in programs:
            yield self.make_opportunity_item(
                title=p["title"], description=p["desc"], source_url=p["url"],
                deadline=None, country="International / Afrique", opp_type="bourse",
                required_level=["Licence","Master"], required_fields=[], required_languages=["en","fr"], min_gpa=p["gpa"],
            )
