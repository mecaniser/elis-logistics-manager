#!/usr/bin/env python3
"""
Backfill missing settlement miles using weekly diesel prices, truck MPG, and fuel-card discounts.
"""
import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import SessionLocal
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.services.diesel_price_service import EIA_API_KEY, maybe_populate_estimated_miles

CHUNK_SIZE = 25


def backfill(dry_run: bool = False, refresh_estimated: bool = False) -> bool:
    if not EIA_API_KEY:
        print("Backfill aborted: EIA_API_KEY is not configured.")
        return False

    db = SessionLocal()
    try:
        candidate_query = (
            db.query(Settlement, Truck)
            .join(Truck, Truck.id == Settlement.truck_id)
            .filter(Truck.vehicle_type == "truck")
            .filter(Settlement.source_settlement_id.is_(None))
            .order_by(Settlement.id.asc())
        )
        if not refresh_estimated:
            candidate_query = candidate_query.filter(Settlement.miles_driven.is_(None))
        candidates = candidate_query.all()

        updated = 0
        skipped = 0
        print(
            "Checking "
            f"{len(candidates)} truck settlements "
            f"({'missing miles or previously estimated miles' if refresh_estimated else 'with missing miles'})"
        )

        for idx, (settlement, truck) in enumerate(candidates, start=1):
            settlement_data = {
                "settlement_date": settlement.settlement_date,
                "week_start": settlement.week_start,
                "week_end": settlement.week_end,
                "miles_driven": settlement.miles_driven,
                "expense_categories": settlement.expense_categories,
                "overview_amounts": settlement.overview_amounts,
            }

            changed = maybe_populate_estimated_miles(
                settlement_data,
                mpg=float(truck.estimated_mpg or 6.5),
                discount_per_gallon=float(truck.fuel_card_discount_per_gallon or 0.0),
                overwrite_existing_estimate=refresh_estimated,
            )
            if not changed:
                skipped += 1
                continue

            if dry_run:
                print(
                    f"  WOULD UPDATE settlement #{settlement.id} "
                    f"({truck.name}, {settlement.settlement_date}): "
                    f"miles={settlement_data['miles_driven']}, "
                    f"effective_price={settlement_data['overview_amounts'].get('effective_fuel_price_per_gallon')}"
                )
            else:
                settlement.miles_driven = settlement_data["miles_driven"]
                settlement.overview_amounts = settlement_data["overview_amounts"]
                db.add(settlement)
            updated += 1

            if not dry_run and idx % CHUNK_SIZE == 0:
                db.commit()

        if not dry_run:
            db.commit()

        print(
            f"Backfill complete: {'would update' if dry_run else 'updated'} {updated} settlements; "
            f"skipped {skipped}"
        )
        return True
    except Exception as exc:
        db.rollback()
        print(f"Backfill failed: {exc}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print changes without committing")
    parser.add_argument(
        "--refresh-estimated",
        action="store_true",
        help="Recalculate rows that already have estimated miles stored in overview_amounts",
    )
    args = parser.parse_args()

    success = backfill(dry_run=args.dry_run, refresh_estimated=args.refresh_estimated)
    if not success:
        sys.exit(1)
