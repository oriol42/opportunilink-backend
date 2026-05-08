# app/celery_app.py
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
    # Alertes deadlines — tous les jours à 8h
    "send-deadline-alerts-daily": {
        "task": "app.tasks.alert_tasks.send_deadline_alerts",
        "schedule": crontab(hour=8, minute=0),
    },
    # OpportunityDesk — bourses/stages Afrique — toutes les 12h
    "crawl-opportunity-desk-twice-daily": {
        "task": "crawl_opportunity_desk",
        "schedule": crontab(hour="6,18", minute=0),
    },
    # Remotive — emplois remote tech — tous les jours à 7h
    "crawl-remotive-daily": {
        "task": "crawl_remotive",
        "schedule": crontab(hour=7, minute=0),
    },
    # The Muse — emplois internationaux — tous les jours à 7h30
    "crawl-the-muse-daily": {
        "task": "crawl_the_muse",
        "schedule": crontab(hour=7, minute=30),
    },
}
