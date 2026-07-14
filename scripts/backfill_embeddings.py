# scripts/backfill_embeddings.py
# A lancer UNE FOIS pour calculer les embeddings des users et opportunites
# deja en base, avant que les hooks (persist_ai_classification / update profil)
# ne prennent le relais pour les nouvelles donnees.
#
# Usage :
#   cd opportunilink-backend
#   python scripts/backfill_embeddings.py

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.opportunity import Opportunity
from app.models.user import User
from app.services.embeddings import (
    embed_passage, embed_query, build_opportunity_text, build_user_profile_text,
)


def main():
    db = SessionLocal()
    try:
        opps = db.query(Opportunity).filter(
            Opportunity.is_active == True, Opportunity.embedding.is_(None)
        ).all()
        print(f"{len(opps)} opportunites sans embedding.")
        for i, opp in enumerate(opps, 1):
            try:
                opp.embedding = embed_passage(build_opportunity_text(opp))
                db.add(opp)
                if i % 20 == 0:
                    db.commit()
                    print(f"[{i}/{len(opps)}] opportunites traitees")
            except Exception as e:
                print(f"[{i}/{len(opps)}] ERREUR opp {opp.id}: {e}")
        db.commit()
        print("Opportunites : termine.\\n")

        users = db.query(User).filter(
            User.is_active == True, User.skills_embedding.is_(None)
        ).all()
        print(f"{len(users)} utilisateurs sans embedding.")
        for i, user in enumerate(users, 1):
            try:
                text = build_user_profile_text(user)
                if text.strip():
                    user.skills_embedding = embed_query(text)
                    db.add(user)
                if i % 20 == 0:
                    db.commit()
                    print(f"[{i}/{len(users)}] utilisateurs traites")
            except Exception as e:
                print(f"[{i}/{len(users)}] ERREUR user {user.id}: {e}")
        db.commit()
        print("Utilisateurs : termine.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
