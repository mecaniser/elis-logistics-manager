#!/usr/bin/env python3
"""
Backfill truck settlements to the current default trailer income split.

Vehicle defaults are used when new settlements are created. This script reapplies
the current truck-level default trailer allocation to existing source settlements
and reconciles the managed trailer-income child settlement.
"""
import argparse
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

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

DEFAULT_FROM_DATE = date(2026, 1, 1)


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def get_child_settlement(db, source_settlement_id: int) -> Optional[Settlement]:
    return (
        db.query(Settlement)
        .filter(Settlement.source_settlement_id == source_settlement_id)
        .first()
    )


def reconcile_accounting(db, *settlements: Settlement) -> None:
    for settlement in settlements:
        if not settlement:
            continue
        delete_settlement_journal_entry(db, settlement.id, auto_commit=False)
        create_settlement_journal_entry(db, settlement, auto_commit=False)


def backfill(
    dry_run: bool = False,
    from_date: Optional[date] = DEFAULT_FROM_DATE,
    truck_id: Optional[int] = None,
) -> bool:
    db = SessionLocal()
    affected_vehicle_ids = set()

    try:
        query = (
            db.query(Settlement)
            .join(Truck, Truck.id == Settlement.truck_id)
            .filter(Truck.vehicle_type == "truck")
            .filter(Truck.default_trailer_id.isnot(None))
            .filter(Truck.default_trailer_income_split_amount.isnot(None))
            .filter(Truck.default_trailer_income_split_amount > 0)
            .filter(Settlement.source_settlement_id.is_(None))
            .order_by(Settlement.settlement_date.asc(), Settlement.id.asc())
        )
        if from_date:
            query = query.filter(Settlement.settlement_date >= from_date)
        if truck_id:
            query = query.filter(Settlement.truck_id == truck_id)

        source_settlements = query.all()
        changed_count = 0
        skipped_count = 0

        print(
            f"Checking {len(source_settlements)} source settlements "
            f"({'all dates' if from_date is None else f'from {from_date.isoformat()}'})"
        )

        for source in source_settlements:
            truck = db.query(Truck).filter(Truck.id == source.truck_id).first()
            trailer = (
                db.query(Truck)
                .filter(
                    Truck.id == truck.default_trailer_id,
                    Truck.tenant_id == truck.tenant_id,
                    Truck.vehicle_type == "trailer",
                )
                .first()
                if truck
                else None
            )
            if not truck or not trailer:
                print(f"  SKIP settlement #{source.id}: default trailer not found")
                skipped_count += 1
                continue

            old_split = money(source.trailer_income_split_amount)
            new_split = money(truck.default_trailer_income_split_amount)
            if old_split == new_split and source.trailer_income_split_trailer_id == trailer.id:
                skipped_count += 1
                continue

            raw_gross_after_other_deductions = money(source.gross_revenue) + old_split
            raw_net_after_other_deductions = money(source.net_profit) + old_split
            if new_split > raw_gross_after_other_deductions:
                print(
                    f"  SKIP settlement #{source.id}: new split ${new_split} exceeds "
                    f"available gross ${raw_gross_after_other_deductions}"
                )
                skipped_count += 1
                continue

            child = get_child_settlement(db, source.id)
            trailer_expenses = money(child.expenses if child else 0)
            trailer_expense_categories = child.expense_categories if child else None
            new_source_gross = raw_gross_after_other_deductions - new_split
            new_source_net = raw_net_after_other_deductions - new_split
            new_child_net = new_split - trailer_expenses

            print(
                f"  {'WOULD UPDATE' if dry_run else 'UPDATE'} settlement #{source.id} "
                f"{source.settlement_date}: split ${old_split} -> ${new_split}; "
                f"truck profit ${money(source.net_profit)} -> ${new_source_net}; "
                f"trailer profit ${money(child.net_profit if child else 0)} -> ${new_child_net}"
            )

            changed_count += 1
            affected_vehicle_ids.update([truck.id, trailer.id])

            if dry_run:
                continue

            source.gross_revenue = new_source_gross
            source.net_profit = new_source_net
            source.trailer_income_split_trailer_id = trailer.id
            source.trailer_income_split_amount = new_split
            db.add(source)
            db.flush()

            if child:
                child.truck_id = trailer.id
                child.settlement_date = source.settlement_date
                child.week_start = source.week_start
                child.week_end = source.week_end
                child.gross_revenue = new_split
                child.expenses = trailer_expenses
                child.expense_categories = trailer_expense_categories
                child.net_profit = new_child_net
                child.pdf_file_path = source.pdf_file_path
                child.settlement_type = "Trailer Income Split"
            else:
                child = Settlement(
                    truck_id=trailer.id,
                    settlement_date=source.settlement_date,
                    week_start=source.week_start,
                    week_end=source.week_end,
                    gross_revenue=new_split,
                    expenses=trailer_expenses,
                    expense_categories=trailer_expense_categories,
                    net_profit=new_child_net,
                    pdf_file_path=source.pdf_file_path,
                    settlement_type="Trailer Income Split",
                    source_settlement_id=source.id,
                )
            db.add(child)
            db.flush()
            reconcile_accounting(db, source, child)

        if not dry_run:
            for vehicle_id in affected_vehicle_ids:
                vehicle = db.query(Truck).filter(Truck.id == vehicle_id).first()
                if vehicle:
                    sync_current_loan_balance(db, vehicle)
            db.commit()

        print(
            f"Backfill complete: {'would update' if dry_run else 'updated'} "
            f"{changed_count} settlements; skipped {skipped_count}"
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
    parser.add_argument("--all-dates", action="store_true", help="Update all matching settlements instead of 2026+ only")
    parser.add_argument("--from-date", help="Update settlements on or after YYYY-MM-DD; default is 2026-01-01")
    parser.add_argument("--truck-id", type=int, help="Only update one source truck")
    args = parser.parse_args()

    selected_from_date = None if args.all_dates else DEFAULT_FROM_DATE
    if args.from_date:
        selected_from_date = date.fromisoformat(args.from_date)

    success = backfill(
        dry_run=args.dry_run,
        from_date=selected_from_date,
        truck_id=args.truck_id,
    )
    if not success:
        sys.exit(1)
