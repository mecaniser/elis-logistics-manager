#!/usr/bin/env python3
"""
Remove managed trailer split rows before a trailer was attached to an owned truck.

This preserves standalone/manual trailer rental settlements and only removes
derived rows where source_settlement_id points back to a truck settlement.
"""
import argparse
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import SessionLocal
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.services.accounting_service import (
    create_settlement_journal_entry,
    delete_settlement_journal_entry,
)
from app.services.loan_balance_service import sync_current_loan_balance


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def cleanup(trailer_id: int, before_date: date, dry_run: bool = False) -> bool:
    db = SessionLocal()
    affected_vehicle_ids = {trailer_id}

    try:
        managed_rows = (
            db.query(Settlement)
            .filter(Settlement.truck_id == trailer_id)
            .filter(Settlement.source_settlement_id.isnot(None))
            .filter(Settlement.settlement_date < before_date)
            .order_by(Settlement.settlement_date.asc(), Settlement.id.asc())
            .all()
        )

        print(
            f"Checking {len(managed_rows)} managed trailer split rows "
            f"for trailer #{trailer_id} before {before_date.isoformat()}"
        )

        removed_count = 0
        skipped_count = 0
        for child in managed_rows:
            source = db.query(Settlement).filter(Settlement.id == child.source_settlement_id).first()
            if not source:
                print(f"  SKIP child #{child.id}: source settlement #{child.source_settlement_id} not found")
                skipped_count += 1
                continue

            split_amount = money(source.trailer_income_split_amount)
            if split_amount <= 0:
                print(f"  SKIP child #{child.id}: source settlement #{source.id} has no split amount")
                skipped_count += 1
                continue

            restored_gross = money(source.gross_revenue) + split_amount
            restored_net = money(source.net_profit) + split_amount
            print(
                f"  {'WOULD REMOVE' if dry_run else 'REMOVE'} child #{child.id} "
                f"{child.settlement_date}; restore source #{source.id} "
                f"gross ${money(source.gross_revenue)} -> ${restored_gross}, "
                f"net ${money(source.net_profit)} -> ${restored_net}, "
                f"clear split ${split_amount}"
            )
            removed_count += 1
            affected_vehicle_ids.add(source.truck_id)

            if dry_run:
                continue

            delete_settlement_journal_entry(db, child.id, auto_commit=False)
            delete_settlement_journal_entry(db, source.id, auto_commit=False)

            source.gross_revenue = restored_gross
            source.net_profit = restored_net
            source.trailer_income_split_trailer_id = None
            source.trailer_income_split_amount = None
            db.add(source)
            db.flush()

            db.delete(child)
            db.flush()
            create_settlement_journal_entry(db, source, auto_commit=False)

        if not dry_run:
            for vehicle_id in affected_vehicle_ids:
                vehicle = db.query(Truck).filter(Truck.id == vehicle_id).first()
                if vehicle:
                    sync_current_loan_balance(db, vehicle)
            db.commit()

        print(
            f"Cleanup complete: {'would remove' if dry_run else 'removed'} "
            f"{removed_count} managed rows; skipped {skipped_count}"
        )
        return True
    except Exception as exc:
        db.rollback()
        print(f"Cleanup failed: {exc}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trailer-id", type=int, required=True, help="Trailer vehicle ID to clean")
    parser.add_argument("--before-date", required=True, help="Remove managed splits before YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without committing")
    args = parser.parse_args()

    success = cleanup(
        trailer_id=args.trailer_id,
        before_date=date.fromisoformat(args.before_date),
        dry_run=args.dry_run,
    )
    if not success:
        sys.exit(1)
