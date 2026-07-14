import sys
import os
import re
import uuid
import logging
import unicodedata
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal
from app.models.opportunity import Opportunity
from app.services.quality import looks_expired_by_academic_year

logger = logging.getLogger(__name__)


# ─── Constants ─────────────────────────────────────────────────────────────────

MIN_DESCRIPTION_LENGTH = 80

VALID_TYPES = {"bourse", "stage", "emploi", "echange", "concours", "formation"}

TYPE_ALIASES = {
    "internship": "stage", "job": "emploi", "scholarship": "bourse",
    "fellowship": "bourse", "exchange": "echange", "course": "formation",
    "training": "formation", "competition": "concours",
}

COUNTRY_NORMALIZE = {
    "germany": "Allemagne", "deutschland": "Allemagne",
    "france": "France",
    "usa": "États-Unis", "united states": "États-Unis",
    "uk": "Royaume-Uni", "united kingdom": "Royaume-Uni",
    "canada": "Canada", "australia": "Australie",
    "netherlands": "Pays-Bas", "holland": "Pays-Bas",
    "sweden": "Suède", "norway": "Norvège",
    "china": "Chine", "japan": "Japon",
    "south africa": "Afrique du Sud",
    "nigeria": "Nigeria", "cameroon": "Cameroun",
    "kenya": "Kenya", "ghana": "Ghana",
    "belgium": "Belgique", "switzerland": "Suisse",
    "austria": "Autriche", "south korea": "Corée du Sud",
    "morocco": "Maroc", "senegal": "Sénégal",
}

SHORTCODE_PATTERNS = [
    r"\[/?[a-zA-Z_-]+[^\]]*\]",   # [shortcode] WordPress
    r"\{\{[^}]+\}\}",              # {{template}}
    r"<!--.*?-->",                  # commentaires HTML
    r"&[a-zA-Z]+;",                # &amp; &nbsp; etc.
    r"&#\d+;",                     # &#160; etc.
]

# Patterns de "bruit" récurrents dans les descriptions scrapées
NOISE_PATTERNS = [
    r"(Applications? are open for the\s*\.)",   # lien vide non résolu
    r"(Click here to apply\.?)",
    r"(For more information,? visit\.?$)",
    r"(Visit the official website\.?)",
    r"(Apply now\.?$)",
    r"(Read more\.?$)",
]

# Langues : on cherche des mots-clés ENTIERS (word boundary \b)
# pour éviter "ineligible" → "de", "engagement" → "en", etc.
LANGUAGE_PATTERNS = {
    "en": [r"\benglish\b", r"\banglais\b"],
    "fr": [r"\bfrench\b", r"\bfrançais\b", r"\bfrancais\b", r"\bfrancophone\b"],
    "de": [r"\bgerman\b", r"\bdeutsch\b", r"\ballemand\b"],
    "es": [r"\bspanish\b", r"\bespagnol\b"],
    "pt": [r"\bportuguese\b", r"\bportugais\b"],
    "zh": [r"\bchinese\b", r"\bchinois\b", r"\bmandarin\b"],
    "ar": [r"\barabic\b", r"\barabe\b"],
}


# ─── Text Cleaning ─────────────────────────────────────────────────────────────

def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def clean_shortcodes(text: str) -> str:
    for pattern in SHORTCODE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.DOTALL)
    return text


def clean_noise(text: str) -> str:
    """Supprime les phrases parasites récurrentes dans les descriptions scrapées."""
    for pattern in NOISE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return text


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """Pipeline complet de nettoyage : HTML → shortcodes → bruit → espaces → invisibles."""
    if not text:
        return ""
    text = clean_html(text)
    text = clean_shortcodes(text)
    text = clean_noise(text)
    text = normalize_whitespace(text)
    text = "".join(c for c in text if unicodedata.category(c)[0] != "C")
    return text.strip()


def normalize_country(country: str) -> str:
    if not country:
        return "International"
    lower = country.lower().strip()
    for key, normalized in COUNTRY_NORMALIZE.items():
        if key in lower:
            return normalized
    return country.strip()


def normalize_type(opp_type: str) -> str:
    if not opp_type:
        return "bourse"
    lower = opp_type.lower().strip()
    if lower in VALID_TYPES:
        return lower
    for alias, valid in TYPE_ALIASES.items():
        if alias in lower:
            return valid
    return "bourse"


def detect_languages(text: str) -> list:
    """
    Détecte les langues requises avec word boundaries (\b).
    Évite les faux positifs : 'ineligible' ne déclenche plus 'de'.
    """
    text_lower = text.lower()
    detected = []
    for lang_code, patterns in LANGUAGE_PATTERNS.items():
        if any(re.search(p, text_lower) for p in patterns):
            detected.append(lang_code)
    return detected if detected else ["en"]


def slugify_title(title: str) -> str:
    """Normalise un titre pour comparer les doublons (ignore ponctuation + années)."""
    title = title.lower()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\b20\d\d\b", "", title)
    title = re.sub(r"\b202\d-?202\d\b", "", title)
    return normalize_whitespace(title)


def is_duplicate_title(title: str, db) -> bool:
    """Vérifie si un titre similaire (80%+ de mots communs) existe déjà en DB."""
    slug = slugify_title(title)
    if len(slug) < 10:
        return False

    existing_titles = db.query(Opportunity.title).filter(
        Opportunity.is_active == True
    ).all()

    words_new = set(slug.split())
    if not words_new:
        return False

    for (existing_title,) in existing_titles:
        existing_slug = slugify_title(existing_title)
        words_existing = set(existing_slug.split())
        if not words_existing:
            continue
        common = words_new & words_existing
        similarity = len(common) / max(len(words_new), len(words_existing))
        if similarity >= 0.80:
            return True

    return False


# ─── Pipeline ──────────────────────────────────────────────────────────────────

class OpportunityPipeline:
    """
    Pipeline Scrapy : nettoyage → validation → déduplication → sauvegarde.
    """

    def open_spider(self, spider):
        self.db = SessionLocal()
        self.saved_count = 0
        self.skipped_count = 0

    def close_spider(self, spider):
        logger.info(
            f"[pipeline] Spider '{spider.name}' terminé — "
            f"{self.saved_count} sauvegardées, {self.skipped_count} ignorées"
        )
        self.db.close()

    def process_item(self, item, spider):
        try:
            # Étape 1 — Nettoyage
            title = clean_text(item.get("title", ""))
            description = clean_text(item.get("description", ""))
            country = normalize_country(item.get("country", "International"))
            opp_type = normalize_type(item.get("type", "bourse"))

            # Fix langues : on re-détecte depuis la description nettoyée
            # plutôt que de faire confiance aux langues du spider (faux positifs)
            raw_languages = item.get("required_languages", [])
            if raw_languages:
                # Revalide : garde seulement les codes connus
                known_codes = set(LANGUAGE_PATTERNS.keys())
                languages = [l for l in raw_languages if l in known_codes]
                # Si rien de valide, re-détecte depuis le texte
                if not languages:
                    languages = detect_languages(title + " " + description)
            else:
                languages = detect_languages(title + " " + description)

            # Étape 2 — Validation qualité minimale
            if not title or len(title) < 10:
                logger.warning(f"[pipeline] ✗ Titre trop court : '{title[:50]}'")
                self.skipped_count += 1
                return item

            if len(description) < MIN_DESCRIPTION_LENGTH:
                logger.warning(
                    f"[pipeline] ✗ Description trop courte ({len(description)} chars) : '{title[:60]}'"
                )
                self.skipped_count += 1
                return item

            # Certains spiders n'ont pas de vrai corps de texte a scraper (page
            # qui ne fait que pointer vers un PDF, par ex.) et recyclent le titre
            # comme description. Une description longue peut donc quand meme
            # etre "fausse" — on compare sa similarite au titre, pas juste sa taille.
            title_vs_desc = SequenceMatcher(
                None, title.lower(), description[: len(title) + 20].lower()
            ).ratio()
            if title_vs_desc > 0.85:
                logger.warning(
                    f"[pipeline] ✗ Description quasi-identique au titre "
                    f"(similarite {title_vs_desc:.2f}) : '{title[:60]}'"
                )
                self.skipped_count += 1
                return item

            # Sans deadline explicite, une opportunite qui mentionne une annee
            # academique deja terminee (ex: 2023/2024) resterait "active" pour
            # toujours dans le feed — on la rejette directement a l'entree.
            if not item.get("deadline") and looks_expired_by_academic_year(title, description):
                logger.warning(
                    f"[pipeline] ✗ Annee academique perimee detectee : '{title[:60]}'"
                )
                self.skipped_count += 1
                return item

            # Étape 3 — Déduplication URL exacte
            source_url = item.get("source_url", "")
            if source_url:
                exists = self.db.query(Opportunity).filter(
                    Opportunity.source_url == source_url
                ).first()
                if exists:
                    logger.debug(f"[pipeline] ✗ URL en DB : '{title[:60]}'")
                    self.skipped_count += 1
                    return item

            # Étape 4 — Déduplication titre similaire
            if is_duplicate_title(title, self.db):
                logger.info(f"[pipeline] ✗ Titre similaire en DB : '{title[:60]}'")
                self.skipped_count += 1
                return item

            # Étape 5 — Sauvegarde
            opp = Opportunity(
                id=uuid.uuid4(),
                title=title[:200],
                description=description[:3000],
                source_url=source_url,
                deadline=item.get("deadline"),
                country=country,
                type=opp_type,
                required_level=item.get("required_level", []),
                required_fields=item.get("required_fields", []),
                required_languages=languages,
                min_gpa=item.get("min_gpa"),
                reliability_score=item.get("reliability_score", 70),
                is_verified=False,
                is_scraped=True,
                is_active=True,
            )
            self.db.add(opp)
            self.db.commit()
            self.saved_count += 1
            logger.info(f"[pipeline] ✓ '{title[:60]}' [{opp_type}] — {country} | langs={languages}")

        except Exception as e:
            self.db.rollback()
            logger.error(
                f"[pipeline] ✗ Erreur '{item.get('title', '?')[:60]}' : {e}",
                exc_info=True,
            )

        return item
