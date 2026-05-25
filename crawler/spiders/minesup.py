# crawler/spiders/minesup.py
# MINESUP — Ministère de l'Enseignement Supérieur du Cameroun
# Bourses gouvernementales, concours, appels à candidatures.
# Site: https://www.minesup.gov.cm

import scrapy
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crawler.spiders.base_spider import BaseOpportunitySpider


class MinesupSpider(BaseOpportunitySpider):
    name = "minesup"
    allowed_domains = ["minesup.gov.cm"]

    start_urls = [
        "https://www.minesup.gov.cm/index.php/actualites/bourses",
        "https://www.minesup.gov.cm/index.php/actualites/appels-a-candidatures",
        "https://www.minesup.gov.cm/index.php/actualites",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": False,  # Site gouvernemental sans robots.txt strict
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def parse(self, response):
        self.logger.info(f"[minesup] Parsing: {response.url}")

        # Stratégie 1 : liens d'articles dans la liste
        links = (
            response.css("article a::attr(href)").getall()
            or response.css(".item-title a::attr(href)").getall()
            or response.css("h2 a::attr(href)").getall()
            or response.css("h3 a::attr(href)").getall()
            or response.css("a.readmore::attr(href)").getall()
        )

        # Mots-clés pertinents pour filtrer
        keywords = [
            "bourse", "candidature", "appel", "concours",
            "stage", "master", "doctorat", "scholarship",
            "formation", "programme"
        ]
        filtered = [
            l for l in links
            if l and any(k in l.lower() for k in keywords)
        ]

        # Si pas de filtre par URL, on prend tous les liens internes
        if not filtered:
            filtered = [
                l for l in links
                if l and ("minesup.gov.cm" in l or l.startswith("/"))
            ]

        self.logger.info(f"[minesup] {len(filtered)} liens trouvés")

        for link in filtered[:10]:
            yield scrapy.Request(
                response.urljoin(link),
                callback=self.parse_detail,
                errback=self.errback,
            )

        # Pagination
        next_page = (
            response.css("a.next::attr(href)").get()
            or response.css("li.next a::attr(href)").get()
            or response.css("[rel='next']::attr(href)").get()
        )
        if next_page:
            yield scrapy.Request(response.urljoin(next_page), callback=self.parse)

    def parse_detail(self, response):
        title = (
            response.css("h1.page-header::text").get()
            or response.css("h1.article-title::text").get()
            or response.css("h1::text").get()
            or response.css("h2.title::text").get()
            or ""
        ).strip()

        if not title or len(title) < 5:
            self.logger.warning(f"[minesup] Pas de titre: {response.url}")
            return

        # Description
        paragraphs = (
            response.css(".article-body p::text").getall()
            or response.css(".item-page p::text").getall()
            or response.css("article p::text").getall()
            or response.css(".content p::text").getall()
            or response.css("p::text").getall()
        )
        description = " ".join(
            p.strip() for p in paragraphs[:8] if len(p.strip()) > 20
        )
        if not description:
            description = (
                f"MINESUP — {title}. "
                "Consultez le site officiel du Ministère de l'Enseignement Supérieur "
                "du Cameroun pour les détails complets."
            )

        # Deadline
        full_text = " ".join(response.css("*::text").getall())
        deadline = self._extract_deadline(full_text)

        # Type d'opportunité
        text_lower = (title + " " + description).lower()
        if any(w in text_lower for w in ["bourse", "scholarship", "fellowship", "allocation"]):
            opp_type = "bourse"
        elif any(w in text_lower for w in ["stage", "internship"]):
            opp_type = "stage"
        elif any(w in text_lower for w in ["concours", "examen", "recrutement"]):
            opp_type = "concours"
        elif any(w in text_lower for w in ["emploi", "poste", "recrutement", "offre d'emploi"]):
            opp_type = "emploi"
        else:
            opp_type = "bourse"

        # Niveau d'études
        levels = []
        if any(w in text_lower for w in ["licence", "bachelor", "l1", "l2", "l3", "undergraduate"]):
            levels.append("Licence")
        if any(w in text_lower for w in ["master", "msc", "m1", "m2", "mba"]):
            levels.append("Master")
        if any(w in text_lower for w in ["doctorat", "phd", "thèse", "doctoral"]):
            levels.append("Doctorat")
        if any(w in text_lower for w in ["bts", "hnd", "technicien"]):
            levels.append("BTS")
        if not levels:
            levels = ["Licence", "Master", "Doctorat"]

        # Pays destination
        countries = {
            "france": "France", "allemagne": "Allemagne", "canada": "Canada",
            "usa": "États-Unis", "chine": "Chine", "maroc": "Maroc",
            "belgique": "Belgique", "royaume-uni": "Royaume-Uni",
            "cameroun": "Cameroun", "afrique": "International (Afrique)",
        }
        country = "International"
        for keyword, country_name in countries.items():
            if keyword in text_lower:
                country = country_name
                break

        yield self.make_opportunity_item(
            title=title,
            description=description[:2000],
            source_url=response.url,
            deadline=deadline,
            country=country,
            opp_type=opp_type,
            required_level=levels,
            required_fields=[],
            required_languages=["fr"],
            min_gpa=None,
        )

    def _extract_deadline(self, text: str):
        patterns = [
            r"[Dd]ate limite[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Dd]eadline[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Cc]l[ôo]ture[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Aa]vant le[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"[Jj]usqu.au[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
            r"au plus tard le[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4})",
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return None

    def errback(self, failure):
        self.logger.error(f"[minesup] Erreur: {failure.request.url} — {failure.value}")
