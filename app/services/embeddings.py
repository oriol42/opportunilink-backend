# app/services/embeddings.py
# Embeddings semantiques pour le matching profil <-> opportunite.
# Utilise fastembed (ONNX, pas de torch) — leger, adapte a l'hebergement Render.

import logging
import math

logger = logging.getLogger(__name__)

_model = None
EMBEDDING_DIM = 384
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def get_embedding_model():
    """
    Charge le modele une seule fois (singleton).
    Le premier appel telecharge le modele (~130MB, mis en cache sur disque).
    Les appels suivants reutilisent l'instance deja chargee en memoire.
    """
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        logger.info("Chargement du modele d'embeddings (premier appel)...")
        _model = TextEmbedding(model_name=MODEL_NAME)
        logger.info("Modele d'embeddings pret")
    return _model


def embed_passage(text: str) -> list[float]:
    """Encode un texte 'document' (ex: description d'opportunite)."""
    if not text or not text.strip():
        return [0.0] * EMBEDDING_DIM
    model = get_embedding_model()
    vector = next(model.embed([text[:2000]]))
    return vector.tolist()


def embed_query(text: str) -> list[float]:
    """Encode un texte 'requete' (ex: profil utilisateur)."""
    if not text or not text.strip():
        return [0.0] * EMBEDDING_DIM
    model = get_embedding_model()
    vector = next(model.embed([text[:2000]]))
    return vector.tolist()


def cosine_similarity(a, b) -> float:
    """Similarite cosinus entre deux vecteurs. Retourne une valeur entre -1 et 1."""
    if a is None or b is None:
        return 0.0
    a, b = list(a), list(b)
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_user_profile_text(user) -> str:
    """Texte representatif du profil : filiere + competences + objectifs."""
    parts = []
    if user.field:
        parts.append(user.field)
    if user.skills:
        parts.append(", ".join(user.skills))
    if user.objectives:
        parts.append(", ".join(user.objectives))
    return " | ".join(parts)


def build_opportunity_text(opp) -> str:
    """Texte representatif de l'opportunite : titre + description."""
    parts = [opp.title or ""]
    if opp.description:
        parts.append(opp.description[:1500])
    return " | ".join(parts)
