# app/tasks/crawler_tasks.py
import subprocess
import logging
import os
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

# All active spiders — add new ones here as we build them
SPIDERS = ["opportunity_desk", "remotive", "the_muse"]


def _run_spider(spider_name: str, max_items: int = 100) -> dict:
    """Run a single Scrapy spider in a subprocess."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        [
            "scrapy", "crawl", spider_name,
            "-s", f"CLOSESPIDER_ITEMCOUNT={max_items}",
            "-s", "LOG_LEVEL=WARNING",
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode == 0:
        logger.info(f"Spider '{spider_name}' completed successfully")
        return {"status": "success", "spider": spider_name}
    else:
        logger.error(f"Spider '{spider_name}' failed: {result.stderr[:500]}")
        return {"status": "error", "spider": spider_name, "error": result.stderr[:500]}


@celery_app.task(name="crawl_opportunity_desk")
def crawl_opportunity_desk():
    """Scrape OpportunityDesk — runs every 12 hours."""
    return _run_spider("opportunity_desk", max_items=50)


@celery_app.task(name="crawl_remotive")
def crawl_remotive():
    """Scrape Remotive remote jobs — runs every 24 hours."""
    return _run_spider("remotive", max_items=100)


@celery_app.task(name="crawl_the_muse")
def crawl_the_muse():
    """Scrape The Muse public API — international jobs — runs every 24 hours."""
    return _run_spider("the_muse", max_items=120)


@celery_app.task(name="crawl_all")
def crawl_all():
    """Run all spiders sequentially. Used for full manual refresh."""
    results = []
    for spider in SPIDERS:
        logger.info(f"Starting spider: {spider}")
        results.append(_run_spider(spider, max_items=50))
    return results
