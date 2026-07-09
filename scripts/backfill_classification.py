# scripts/backfill_classification.py
# A lancer UNE FOIS pour classifier (documents reels + filieres reellement
# concernees) toutes les opportunites deja en base avant que la tache
# periodique Celery ne prenne le relais pour les nouvelles.
#
# Usage :
#   cd opportunilink-backend
#   python scripts/backfill_classification.py

import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.opportunity import Opportunity
from app.services.scoring import persist_ai_classification


def main():
    db = SessionLocal()
    try:
        all_opps = (
            db.query(Opportunity)
            .filter(Opportunity.is_active == True)
            .order_by(Opportunity.created_at.desc())
            .all()
        )
        todo = [
            o for o in all_opps
            if not (o.required_docs and o.required_docs.get("ai_extracted"))
        ]
        print(f"{len(all_opps)} opportunites actives, {len(todo)} a classifier.\\n")

        done, errors = 0, 0
        for i, opp in enumerate(todo, 1):
            try:
                result = persist_ai_classification(db, opp)
                done += 1
                fields = result.get("target_fields") or ["(ouvert a tous)"]
                print(f"[{i}/{len(todo)}] OK  — {opp.title[:60]!r:63} -> {fields}")
            except Exception as e:
                errors += 1
                print(f"[{i}/{len(todo)}] ERREUR — {opp.title[:60]!r}: {e}")
            time.sleep(2.5)  # throttle : reste large sous le rate limit Groq gratuit

        print(f"\\nTermine : {done} classifiees, {errors} erreurs.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
