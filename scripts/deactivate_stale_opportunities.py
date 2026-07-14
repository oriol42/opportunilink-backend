# scripts/deactivate_stale_opportunities.py
# Desactive retroactivement les opportunites deja en base qui mentionnent
# une annee academique perimee (ex: 2023/2024) mais n'ont pas de deadline
# explicite, et qui donc restent "actives" pour toujours dans le feed.
#
# Usage :
#   python scripts/deactivate_stale_opportunities.py               # apercu (rien modifie)
#   python scripts/deactivate_stale_opportunities.py --apply        # applique vraiment

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.opportunity import Opportunity
from app.services.quality import looks_expired_by_academic_year


def main():
    apply_changes = "--apply" in sys.argv
    db = SessionLocal()
    try:
        candidates = db.query(Opportunity).filter(
            Opportunity.is_active == True,
            Opportunity.deadline.is_(None),
        ).all()

        stale = [
            opp for opp in candidates
            if looks_expired_by_academic_year(opp.title or "", opp.description or "")
        ]

        print(f"{len(candidates)} opportunites actives sans deadline examinees.")
        print(f"{len(stale)} detectees comme perimees :\n")
        for opp in stale:
            print(f"  - [{opp.id}] {opp.title[:90]}")

        if not stale:
            print("\nRien a faire.")
            return

        if not apply_changes:
            print(f"\nMode apercu — rien n'a ete modifie.")
            print(f"Relance avec --apply pour desactiver ces {len(stale)} opportunites.")
            return

        for opp in stale:
            opp.is_active = False
        db.commit()
        print(f"\n{len(stale)} opportunites desactivees (is_active = false).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
