BOT_NAME = "opportunilink"

SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

# Respecter les robots.txt
ROBOTSTXT_OBEY = True

# Délai entre requêtes (poli avec les serveurs)
DOWNLOAD_DELAY = 2

# Pipeline pour sauvegarder en DB
ITEM_PIPELINES = {
    "crawler.pipeline.OpportunityPipeline": 300,
}

# Headers pour ne pas être bloqué
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr,en;q=0.5",
}

LOG_LEVEL = "INFO"
