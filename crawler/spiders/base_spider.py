import scrapy
from datetime import datetime


class BaseOpportunitySpider(scrapy.Spider):
    """
    Spider de base. Tous les autres spiders héritent de celui-ci.
    Fournit des méthodes utilitaires communes.
    """

    def make_opportunity_item(
        self,
        title: str,
        description: str,
        source_url: str,
        deadline: str | None,
        country: str,
        opp_type: str,
        required_level: list[str],
        required_fields: list[str],
        required_languages: list[str],
        min_gpa: float | None = None,
    ) -> dict:
        """
        Crée un dictionnaire standardisé pour une opportunité.
        Chaque spider appelle cette méthode pour s'assurer
        que la structure est toujours la même.
        """
        return {
            "title": title.strip(),
            "description": description.strip(),
            "source_url": source_url,
            "deadline": deadline,
            "country": country,
            "type": opp_type,
            "required_level": required_level,
            "required_fields": required_fields,
            "required_languages": required_languages,
            "min_gpa": min_gpa,
            "reliability_score": 80,  # Score de base pour sources officielles
            "is_verified": False,
            "is_scraped": True,
            "scraped_at": datetime.utcnow().isoformat(),
        }
