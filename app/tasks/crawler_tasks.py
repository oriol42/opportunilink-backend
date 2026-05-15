# app/tasks/crawler_tasks.py
import subprocess, logging, os
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

SPIDERS = [
    "opportunity_desk", "remotive", "the_muse", "daad", "campus_france",
    "reliefweb", "auf", "scholars4dev", "mtn_cm", "euraxess",
    "world_bank", "afdb", "unfpa", "coursera_free", "unicameroun",
    "orange_cm", "mastercard_foundation",
]

def _run_spider(spider_name: str, max_items: int = 100) -> dict:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        ["scrapy", "crawl", spider_name, "-s", f"CLOSESPIDER_ITEMCOUNT={max_items}", "-s", "LOG_LEVEL=WARNING"],
        cwd=project_root, capture_output=True, text=True, timeout=300,
    )
    if result.returncode == 0:
        logger.info(f"Spider '{spider_name}' OK")
        return {"status": "success", "spider": spider_name}
    else:
        logger.error(f"Spider '{spider_name}' failed: {result.stderr[:300]}")
        return {"status": "error", "spider": spider_name, "error": result.stderr[:300]}

@celery_app.task(name="crawl_opportunity_desk")
def crawl_opportunity_desk(): return _run_spider("opportunity_desk", 50)

@celery_app.task(name="crawl_remotive")
def crawl_remotive(): return _run_spider("remotive", 100)

@celery_app.task(name="crawl_the_muse")
def crawl_the_muse(): return _run_spider("the_muse", 120)

@celery_app.task(name="crawl_daad")
def crawl_daad(): return _run_spider("daad", 30)

@celery_app.task(name="crawl_campus_france")
def crawl_campus_france(): return _run_spider("campus_france", 30)

@celery_app.task(name="crawl_reliefweb")
def crawl_reliefweb(): return _run_spider("reliefweb", 50)

@celery_app.task(name="crawl_auf")
def crawl_auf(): return _run_spider("auf", 20)

@celery_app.task(name="crawl_scholars4dev")
def crawl_scholars4dev(): return _run_spider("scholars4dev", 30)

@celery_app.task(name="crawl_mtn_cm")
def crawl_mtn_cm(): return _run_spider("mtn_cm", 15)

@celery_app.task(name="crawl_euraxess")
def crawl_euraxess(): return _run_spider("euraxess", 30)

@celery_app.task(name="crawl_world_bank")
def crawl_world_bank(): return _run_spider("world_bank", 30)

@celery_app.task(name="crawl_afdb")
def crawl_afdb(): return _run_spider("afdb", 20)

@celery_app.task(name="crawl_unfpa")
def crawl_unfpa(): return _run_spider("unfpa", 20)

@celery_app.task(name="crawl_coursera_free")
def crawl_coursera_free(): return _run_spider("coursera_free", 50)

@celery_app.task(name="crawl_unicameroun")
def crawl_unicameroun(): return _run_spider("unicameroun", 30)

@celery_app.task(name="crawl_orange_cm")
def crawl_orange_cm(): return _run_spider("orange_cm", 20)

@celery_app.task(name="crawl_mastercard_foundation")
def crawl_mastercard_foundation(): return _run_spider("mastercard_foundation", 20)

@celery_app.task(name="crawl_all")
def crawl_all():
    results = []
    for spider in SPIDERS:
        logger.info(f"Starting spider: {spider}")
        results.append(_run_spider(spider, max_items=50))
    return results
