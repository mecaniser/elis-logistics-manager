"""Backfill specific categories from already-imported deduction details.

Safe to run more than once. It changes only known line descriptions and keeps
the total expense amount unchanged.
"""
from app.database import SessionLocal
from app.models.settlement import Settlement
from app.services.settlement_expense_categories import category_for_deduction


def main() -> None:
    db = SessionLocal()
    updated = 0
    try:
        for settlement in db.query(Settlement).all():
            categories = dict(settlement.expense_categories or {})
            details = settlement.deduction_details or []
            remaining_generic = float(categories.get("deduct") or 0)
            changed = False

            for detail in details:
                category = category_for_deduction(str(detail.get("description") or ""))
                if category == "deduct":
                    continue
                amount = float(detail.get("amount") or 0)
                if amount <= 0:
                    continue
                # Only reclassify money still held in the legacy generic bucket.
                # On a repeated run that bucket is exhausted, making this safe.
                if remaining_generic + 0.001 < amount:
                    continue
                categories[category] = round(float(categories.get(category) or 0) + amount, 2)
                remaining_generic = round(max(0.0, remaining_generic - amount), 2)
                changed = True

            if changed:
                if remaining_generic:
                    categories["deduct"] = remaining_generic
                else:
                    categories.pop("deduct", None)
                settlement.expense_categories = categories
                updated += 1

        db.commit()
        print(f"Updated {updated} settlement(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
