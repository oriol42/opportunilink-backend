import sys
import os

# Permet d'importer les modules FastAPI depuis le crawler
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.opportunity import Opportunity
import uuid
import logging

logger = logging.getLogger(__name__)


class OpportunityPipeline:
    """
    Pipeline Scrapy : reçoit chaque item scrapé et le sauvegarde en DB.
    Si l'opportunité existe déjà (même source_url), elle est ignorée.
    """

    def open_spider(self, spider):
        self.db = SessionLocal()

    def close_spider(self, spider):
        self.db.close()

    def process_item(self, item, spider):
        # Vérifier si l'opportunité existe déjà
        existing = self.db.query(Opportunity).filter(
            Opportunity.source_url == item["source_url"]
        ).first()

        if existing:
            logger.info(f"Deja en DB, ignoree : {item['title']}")
            return item

        # Créer la nouvelle opportunité
        opp = Opportunity(
            id=uuid.uuid4(),
            title=item["title"],
            description=item["description"],
            source_url=item["source_url"],
            deadline=item.get("deadline"),
            country=item["country"],
            type=item["type"],
            required_level=item.get("required_level", []),
            required_fields=item.get("required_fields", []),
            required_languages=item.get("required_languages", []),
            min_gpa=item.get("min_gpa"),
            reliability_score=item.get("reliability_score", 50),
            is_verified=False,
            is_scraped=True,
            is_active=True,
        )

        self.db.add(opp)
        self.db.commit()
        logger.info(f"Sauvegardee : {item['title']}")

        return item
