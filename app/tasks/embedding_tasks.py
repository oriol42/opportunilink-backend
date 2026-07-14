# app/tasks/embedding_tasks.py
# Calcul des embeddings en tache de fond — le modele (~220MB) ne doit
# JAMAIS etre charge dans le process web (limite RAM sur Render), donc
# ce calcul se fait exclusivement ici, cote worker Celery.

import logging
from app.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="recompute_user_embedding")
def recompute_user_embedding(user_id: str):
    from app.models.user import User
    from app.services.embeddings import embed_query, build_user_profile_text

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"recompute_user_embedding: user {user_id} introuvable")
            return
        text = build_user_profile_text(user)
        if text.strip():
            user.skills_embedding = embed_query(text)
            db.add(user)
            db.commit()
            logger.info(f"Embedding recalcule pour user {user_id}")
    except Exception as e:
        logger.warning(f"recompute_user_embedding echoue pour {user_id}: {e}")
    finally:
        db.close()
