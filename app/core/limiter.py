# app/core/limiter.py
# Rate limiting — protège l'API contre les abus et le scraping.
# slowapi est un wrapper autour de limits, compatible FastAPI.

from slowapi import Limiter
from slowapi.util import get_remote_address

# get_remote_address extrait l'IP du client depuis la requête.
# En prod derrière un proxy (Railway/Nginx), il faut configurer
# FORWARDED_ALLOW_IPS côté Railway pour que l'IP réelle passe.
limiter = Limiter(key_func=get_remote_address)
