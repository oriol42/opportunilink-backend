# app/tasks/crawler_tasks.py
import subprocess
import logging
import os
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

SPIDERS = [
    "opportunity_desk",
    "remotive",
    "the_muse",
    "daad",
    "campus_france",
    "reliefweb",
    "auf",
    "scholars4dev",
    "mtn_cm",
    "euraxess",
    "un_jobs",
    "world_bank_jobs",
    "minesup_cm",
    "oms_afro",
    "ifj_journalism",
    "orange_fondation",
]


def _run_spider(spider_name: str, max_items: int = 100) -> dict:
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
        logger.info(f"Spider '{spider_name}' OK")
        return {"status": "success", "spider": spider_name}
    else:
        logger.error(f"Spider '{spider_name}' failed: {result.stderr[:300]}")
        return {"status": "error", "spider": spider_name, "error": result.stderr[:300]}


@celery_app.task(name="crawl_opportunity_desk")
def crawl_opportunity_desk():
    return _run_spider("opportunity_desk", max_items=50)

@celery_app.task(name="crawl_remotive")
def crawl_remotive():
    return _run_spider("remotive", max_items=100)

@celery_app.task(name="crawl_the_muse")
def crawl_the_muse():
    return _run_spider("the_muse", max_items=120)

@celery_app.task(name="crawl_daad")
def crawl_daad():
    return _run_spider("daad", max_items=30)

@celery_app.task(name="crawl_campus_france")
def crawl_campus_france():
    return _run_spider("campus_france", max_items=30)

@celery_app.task(name="crawl_reliefweb")
def crawl_reliefweb():
    return _run_spider("reliefweb", max_items=50)

@celery_app.task(name="crawl_auf")
def crawl_auf():
    return _run_spider("auf", max_items=20)

@celery_app.task(name="crawl_scholars4dev")
def crawl_scholars4dev():
    return _run_spider("scholars4dev", max_items=30)

@celery_app.task(name="crawl_mtn_cm")
def crawl_mtn_cm():
    return _run_spider("mtn_cm", max_items=15)

@celery_app.task(name="crawl_euraxess")
def crawl_euraxess():
    return _run_spider("euraxess", max_items=30)

@celery_app.task(name="crawl_un_jobs")
def crawl_un_jobs():
    return _run_spider("un_jobs", max_items=40)

@celery_app.task(name="crawl_world_bank_jobs")
def crawl_world_bank_jobs():
    return _run_spider("world_bank_jobs", max_items=20)

@celery_app.task(name="crawl_minesup_cm")
def crawl_minesup_cm():
    return _run_spider("minesup_cm", max_items=20)

@celery_app.task(name="crawl_oms_afro")
def crawl_oms_afro():
    return _run_spider("oms_afro", max_items=20)

@celery_app.task(name="crawl_ifj_journalism")
def crawl_ifj_journalism():
    return _run_spider("ifj_journalism", max_items=20)

@celery_app.task(name="crawl_orange_fondation")
def crawl_orange_fondation():
    return _run_spider("orange_fondation", max_items=15)

@celery_app.task(name="crawl_all")
def crawl_all():
    results = []
    for spider in SPIDERS:
        logger.info(f"Starting spider: {spider}")
        results.append(_run_spider(spider, max_items=50))
    return results
