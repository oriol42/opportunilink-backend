# app/services/opportunity_pdf.py
"""
Recupere et extrait le texte d'un PDF lie a une opportunite quand la
description scrapee est trop pauvre pour etre analysee par l IA. Cas frequent :
l'annonce sur le site source n'est qu'un lien vers un PDF officiel, et le
spider n'a alors rien de substantiel a extraire en HTML.

Deux cas geres :
  1. source_url pointe DIRECTEMENT vers un .pdf
  2. source_url est une page HTML qui CONTIENT un lien vers un .pdf
"""
import re
import logging
from urllib.parse import urljoin

import httpx

from app.services.ai_coach import extract_pdf_text

logger = logging.getLogger(__name__)

MAX_PDF_BYTES = 15 * 1024 * 1024  # 15MB — au-dela on abandonne (pas question de
                                    # bloquer le worker Celery sur un fichier enorme)
FETCH_TIMEOUT = 15.0
PDF_TEXT_MAX_CHARS = 3000  # plus large que la description scrapee (1500) car
                             # c'est ici la SEULE source d'info disponible

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OpportuLinkBot/1.0)"}

_PDF_HREF_RE = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.IGNORECASE)


def _looks_like_pdf_url(url: str) -> bool:
    return bool(url) and url.split("?")[0].lower().endswith(".pdf")


def _find_pdf_link_in_html(html: str, base_url: str) -> str | None:
    match = _PDF_HREF_RE.search(html)
    if not match:
        return None
    return urljoin(base_url, match.group(1))


def _download(url: str) -> bytes | None:
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=True, headers=HEADERS) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                content_length = resp.headers.get("content-length")
                if content_length and int(content_length) > MAX_PDF_BYTES:
                    logger.warning(f"[pdf_fetch] PDF trop volumineux ignore : {url}")
                    return None
                chunks = bytearray()
                for chunk in resp.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > MAX_PDF_BYTES:
                        logger.warning(f"[pdf_fetch] PDF trop volumineux (stream) ignore : {url}")
                        return None
                return bytes(chunks)
    except Exception as e:
        logger.warning(f"[pdf_fetch] Echec telechargement {url} : {e}")
        return None


def fetch_pdf_text_for_opportunity(source_url: str) -> dict:
    """
    Retourne :
      - "text" : texte extrait (tronque), "" si rien d'exploitable
      - "pdf_url" : url du PDF trouve, None si aucun
      - "found_but_unreadable" : True si un PDF a ete trouve et telecharge
         mais qu'aucun texte n'a pu en etre extrait (probable scan/image —
         necessiterait de l'OCR, hors scope pour l'instant)
    """
    if not source_url:
        return {"text": "", "pdf_url": None, "found_but_unreadable": False}

    pdf_url = source_url if _looks_like_pdf_url(source_url) else None

    if not pdf_url:
        try:
            with httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=True, headers=HEADERS) as client:
                resp = client.get(source_url)
                resp.raise_for_status()
                pdf_url = _find_pdf_link_in_html(resp.text, source_url)
        except Exception as e:
            logger.warning(f"[pdf_fetch] Echec recuperation page {source_url} : {e}")
            return {"text": "", "pdf_url": None, "found_but_unreadable": False}

    if not pdf_url:
        return {"text": "", "pdf_url": None, "found_but_unreadable": False}

    pdf_bytes = _download(pdf_url)
    if pdf_bytes is None:
        return {"text": "", "pdf_url": pdf_url, "found_but_unreadable": False}

    text = extract_pdf_text(pdf_bytes)
    if not text:
        logger.info(f"[pdf_fetch] PDF trouve mais illisible (scan probable) : {pdf_url}")
        return {"text": "", "pdf_url": pdf_url, "found_but_unreadable": True}

    return {"text": text[:PDF_TEXT_MAX_CHARS], "pdf_url": pdf_url, "found_but_unreadable": False}
