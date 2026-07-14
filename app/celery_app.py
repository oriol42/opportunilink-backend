from celery import Celery
from celery.schedules import crontab
from app.config import settings

redis_url = settings.redis_url or "redis://localhost:6379/0"
ssl_options = {"ssl_cert_reqs": "none"} if redis_url.startswith("rediss://") else {}

celery_app = Celery(
    "opportunilink",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.alert_tasks",
        "app.tasks.crawler_tasks",
        "app.tasks.embedding_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Douala",
    enable_utc=True,
    broker_use_ssl=ssl_options if ssl_options else None,
    redis_backend_use_ssl=ssl_options if ssl_options else None,
)

celery_app.conf.beat_schedule = {

    # ── Alertes ───────────────────────────────────────────────
    "send-deadline-alerts-daily": {
        "task": "app.tasks.alert_tasks.send_deadline_alerts",
        "schedule": crontab(hour=8, minute=0),
    },

    # ── Classification IA (documents + filieres reelles) ──────
    # Une fois par jour : meme avec la cle dediee, on reste sous son propre
    # quota gratuit (~100k tokens/jour ; batch_size=50 ~ 85k tokens).
    "classify-unclassified-opportunities": {
        "task": "classify_unclassified_opportunities",
        "schedule": crontab(hour=3, minute=0),
    },

    # ── Crawlers haute fréquence (2x/jour) ───────────────────
    "crawl-opportunity-desk-twice-daily": {
        "task": "crawl_opportunity_desk",
        "schedule": crontab(hour="6,18", minute=0),
    },
    "crawl-reliefweb-twice-daily": {
        "task": "crawl_reliefweb",
        "schedule": crontab(hour="5,17", minute=30),
    },

    # ── Crawlers quotidiens ───────────────────────────────────
    "crawl-remotive-daily": {
        "task": "crawl_remotive",
        "schedule": crontab(hour=7, minute=0),
    },
    "crawl-the-muse-daily": {
        "task": "crawl_the_muse",
        "schedule": crontab(hour=7, minute=30),
    },
    "crawl-daad-daily": {
        "task": "crawl_daad",
        "schedule": crontab(hour=8, minute=30),
    },
    "crawl-campus-france-daily": {
        "task": "crawl_campus_france",
        "schedule": crontab(hour=9, minute=0),
    },
    "crawl-auf-daily": {
        "task": "crawl_auf",
        "schedule": crontab(hour=9, minute=30),
    },
    "crawl-scholars4dev-daily": {
        "task": "crawl_scholars4dev",
        "schedule": crontab(hour=10, minute=0),
    },
    "crawl-euraxess-daily": {
        "task": "crawl_euraxess",
        "schedule": crontab(hour=10, minute=30),
    },
    "crawl-un-jobs-daily": {
        "task": "crawl_un_jobs",
        "schedule": crontab(hour=11, minute=0),
    },
    "crawl-world-bank-daily": {
        "task": "crawl_world_bank_jobs",
        "schedule": crontab(hour=11, minute=30),
    },
    "crawl-oms-afro-daily": {
        "task": "crawl_oms_afro",
        "schedule": crontab(hour=12, minute=0),
    },
    "crawl-ifj-journalism-daily": {
        "task": "crawl_ifj_journalism",
        "schedule": crontab(hour=12, minute=30),
    },
    "crawl-orange-fondation-daily": {
        "task": "crawl_orange_fondation",
        "schedule": crontab(hour=13, minute=0),
    },

    # ── Crawlers hebdomadaires ────────────────────────────────
    "crawl-mtn-cm-weekly": {
        "task": "crawl_mtn_cm",
        "schedule": crontab(hour=10, minute=30, day_of_week="1"),
    },
    "crawl-minesup-weekly": {
        "task": "crawl_minesup_cm",
        "schedule": crontab(hour=14, minute=0, day_of_week="1,4"),
    },
}
