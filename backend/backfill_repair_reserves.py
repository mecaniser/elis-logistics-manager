#!/usr/bin/env python3
"""
Backfill repair reserve amounts and deposit ledger rows for 2026+ settlements.
"""
import argparse
import sys
from pathlib import Path

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import SessionLocal
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.utils.reserve_regime import RESERVE_REGIME_START_DATE, format_deposit_description

CHUNK_SIZE = 10


def backfill(dry_run: bool = False) -> bool:
    db = SessionLocal()
    try:
        settlements = (
            db.query(Settlement)
            .filter(Settlement.settlement_date >= RESERVE_REGIME_START_DATE)
            .filter(Settlement.repair_reserve_amount.is_(None))
            .order_by(Settlement.id.asc())
            .all()
        )

        pass1_count = 0
        print(f"Pass 1: checking {len(settlements)} settlements missing repair_reserve_amount")
        for idx, settlement in enumerate(settlements, start=1):
            truck = db.query(Truck).filter(Truck.id == settlement.truck_id).first()
            default_amount = truck.default_repair_reserve_amount if truck else None
            if default_amount and default_amount > 0:
                if dry_run:
                    print(
                        f"  WOULD SET settlement #{settlement.id} "
                        f"(truck {truck.name if truck else settlement.truck_id}, {settlement.settlement_date}): "
                        f"repair_reserve_amount={default_amount}"
                    )
                else:
                    settlement.repair_reserve_amount = default_amount
                pass1_count += 1

            if not dry_run and idx % CHUNK_SIZE == 0:
                db.commit()

        if not dry_run:
            db.commit()

        print(
            f"Pass 1 complete: {'would populate' if dry_run else 'populated'} "
            f"repair_reserve_amount on {pass1_count} settlements"
        )

        eligible = (
            db.query(Settlement)
            .filter(Settlement.settlement_date >= RESERVE_REGIME_START_DATE)
            .filter(Settlement.repair_reserve_amount > 0)
            .order_by(Settlement.id.asc())
            .all()
        )

        pass2_create = 0
        pass2_reconcile = 0
        print(f"Pass 2: checking {len(eligible)} eligible settlements for deposit rows")
        for idx, settlement in enumerate(eligible, start=1):
            truck = db.query(Truck).filter(Truck.id == settlement.truck_id).first()
            if not truck:
                print(f"  WARNING: settlement #{settlement.id} has no truck; skipping")
                continue

            existing = (
                db.query(RepairReserveLedger)
                .filter_by(source_type="settlement", source_id=settlement.id, entry_type="deposit")
                .first()
            )

            if existing:
                needs_reconcile = (
                    existing.amount != settlement.repair_reserve_amount
                    or existing.entry_date != settlement.settlement_date
                    or existing.truck_id != settlement.truck_id
                    or existing.tenant_id != truck.tenant_id
                    or existing.description != format_deposit_description(settlement)
                )
                if needs_reconcile:
                    if dry_run:
                        print(
                            f"  WOULD RECONCILE ledger #{existing.id} for settlement #{settlement.id}: "
                            f"amount={existing.amount}->{settlement.repair_reserve_amount}, "
                            f"truck_id={existing.truck_id}->{settlement.truck_id}"
                        )
                    else:
                        existing.amount = settlement.repair_reserve_amount
                        existing.entry_date = settlement.settlement_date
                        existing.truck_id = settlement.truck_id
                        existing.tenant_id = truck.tenant_id
                        existing.description = format_deposit_description(settlement)
                    pass2_reconcile += 1
            else:
                if dry_run:
                    print(
                        f"  WOULD CREATE deposit for settlement #{settlement.id} "
                        f"(truck {truck.name}, {settlement.settlement_date}): "
                        f"tenant={truck.tenant_id} amount={settlement.repair_reserve_amount}"
                    )
                else:
                    db.add(
                        RepairReserveLedger(
                            tenant_id=truck.tenant_id,
                            truck_id=settlement.truck_id,
                            entry_date=settlement.settlement_date,
                            entry_type="deposit",
                            amount=settlement.repair_reserve_amount,
                            description=format_deposit_description(settlement),
                            source_type="settlement",
                            source_id=settlement.id,
                        )
                    )
                pass2_create += 1

            if not dry_run and idx % CHUNK_SIZE == 0:
                db.commit()

        if not dry_run:
            db.commit()

        print(
            f"Pass 2 complete: {'would create' if dry_run else 'created'} {pass2_create} new deposit rows; "
            f"{'would reconcile' if dry_run else 'reconciled'} {pass2_reconcile} existing rows"
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
    args = parser.parse_args()

    success = backfill(dry_run=args.dry_run)
    if not success:
        sys.exit(1)
