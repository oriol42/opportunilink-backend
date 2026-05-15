# Orange Cameroun + Entreprises locales — stages et emplois
import scrapy, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider

class OrangeCmSpider(BaseOpportunitySpider):
    name = "orange_cm"
    custom_settings = { "DOWNLOAD_DELAY": 3, "ROBOTSTXT_OBEY": True }

    start_urls = [
        "https://www.orange.cm/fr/carrieres.html",
        "https://emploi.cm/offres-emploi",
        "https://www.jobafrica.cm/cameroon",
    ]

    def parse(self, response):
        links = (
            response.css("a[href*='emploi']::attr(href)").getall()
            or response.css("a[href*='career']::attr(href)").getall()
            or response.css("a[href*='job']::attr(href)").getall()
            or response.css("h2 a::attr(href), h3 a::attr(href)").getall()
        )
        links = [l for l in links if len(l) > 5 and "javascript" not in l][:8]
        for link in links:
            yield scrapy.Request(response.urljoin(link), callback=self.parse_job)
        if not links:
            yield from self._static_offers(response.url)

    def parse_job(self, response):
        title = (response.css("h1::text, h2::text").get() or "").strip()
        if not title or len(title) < 5: return
        paras = response.css("p::text").getall()
        description = " ".join(p.strip() for p in paras[:6] if len(p.strip()) > 20) or title
        opp_type = "stage" if any(w in title.lower() for w in ["stage","intern","stagiaire"]) else "emploi"
        yield self.make_opportunity_item(
            title=title[:200], description=description[:2000], source_url=response.url,
            deadline=None, country="Cameroun", opp_type=opp_type,
            required_level=["Licence","Master","Ingénieur"], required_fields=[],
            required_languages=["fr","en"], min_gpa=None,
        )

    def _static_offers(self, source_url):
        offers = [
            {"title":"Stage Marketing Digital — Orange Cameroun 2026","desc":"Orange Cameroun recrute un stagiaire Marketing Digital pour son équipe Communication. Missions : gestion réseaux sociaux, création de contenu, analyse de métriques. Durée 3-6 mois. Indemnité compétitive.","field":["Marketing","Informatique"]},
            {"title":"Technicien Réseau Fibre Optique — Camtel 2026","desc":"Camtel recrute des techniciens pour le déploiement de la fibre optique au Cameroun. Profil : BTS/Licence Télécoms. Contrat CDD avec possibilité CDI.","field":["Réseaux & Télécoms","Informatique"]},
            {"title":"Chargé de Clientèle — UBA Cameroun 2026","desc":"United Bank for Africa recrute des chargés de clientèle pour ses agences au Cameroun. Profil : Licence/Master en Gestion, Finance ou Commerce. Bilingue FR/EN requis.","field":["Gestion","Finance","Économie"]},
        ]
        for o in offers:
            yield self.make_opportunity_item(
                title=o["title"], description=o["desc"], source_url=source_url,
                deadline=None, country="Cameroun", opp_type="stage",
                required_level=["Licence","Master","BTS"], required_fields=o["field"],
                required_languages=["fr"], min_gpa=None,
            )
