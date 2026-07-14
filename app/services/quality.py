# app/services/quality.py
# Heuristiques de qualite des donnees, partagees entre le crawler (empeche
# l'entree de mauvaises opportunites) et les scripts de nettoyage (corrige
# celles deja en base).

import re
from datetime import date

# Format annee/annee tres caracteristique des textes administratifs
# camerounais/francophones : "2023/2024", "2023-2024", etc.
ACADEMIC_YEAR_PATTERN = re.compile(r'(20\d{2})\s*[/\-]\s*(20\d{2})')


def looks_expired_by_academic_year(title: str, description: str) -> bool:
    """
    Detecte une opportunite qui mentionne une annee academique DEJA TERMINEE
    (ex: 'au titre de l'annee academique 2023/2024') alors qu'elle n'a pas
    de deadline explicite en base — ce qui la ferait sinon apparaitre comme
    'toujours active' indefiniment dans le feed.

    Heuristique volontairement conservatrice : se declenche seulement si
    l'annee de fin mentionnee remonte a 2 ans ou plus, pour laisser une
    marge et ne pas flaguer par erreur une opportunite de l'annee en cours
    ou a venir.
    """
    text = f"{title} {description}"
    matches = ACADEMIC_YEAR_PATTERN.findall(text)
    if not matches:
        return False

    current_year = date.today().year
    for y1, y2 in matches:
        end_year = max(int(y1), int(y2))
        if end_year <= current_year - 2:
            return True
    return False
