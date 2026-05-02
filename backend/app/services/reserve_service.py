"""
Reserve service helpers.
"""
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.utils.reserve_regime import (
    RESERVE_REGIME_START_DATE,
    format_deposit_description,
    format_withdrawal_description,
)


def _sync_ledger_entry(
    db: Session,
    *,
    source_type: str,
    source_id: int,
    entry_type: str,
    truck_id: int,
    entry_date,
    amount,
    description_fn: Callable[[], str],
    should_write: bool,
) -> Optional[RepairReserveLedger]:
    """Create, update, or delete a single source-owned ledger entry."""
    existing = (
        db.query(RepairReserveLedger)
        .filter_by(source_type=source_type, source_id=source_id, entry_type=entry_type)
        .first()
    )

    normalized_amount = None if amount is None else amount
    in_regime = entry_date is not None and entry_date >= RESERVE_REGIME_START_DATE
    if not (should_write and in_regime and normalized_amount and normalized_amount > 0):
        if existing:
            db.delete(existing)
        return None

    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        return None

    if existing:
        existing.tenant_id = truck.tenant_id
        existing.truck_id = truck_id
        existing.entry_date = entry_date
        existing.amount = normalized_amount
        existing.description = description_fn()
        db.add(existing)
        return existing

    ledger_row = RepairReserveLedger(
        tenant_id=truck.tenant_id,
        truck_id=truck_id,
        entry_date=entry_date,
        entry_type=entry_type,
        amount=normalized_amount,
        description=description_fn(),
        source_type=source_type,
        source_id=source_id,
    )
    db.add(ledger_row)
    return ledger_row


def sync_repair_reserve_ledger(db: Session, settlement: Settlement) -> Optional[RepairReserveLedger]:
    return _sync_ledger_entry(
        db,
        source_type="settlement",
        source_id=settlement.id,
        entry_type="deposit",
        truck_id=settlement.truck_id,
        entry_date=settlement.settlement_date,
        amount=settlement.repair_reserve_amount,
        description_fn=lambda: format_deposit_description(settlement),
        should_write=True,
    )


def sync_repair_reserve_withdrawal(db: Session, repair: Repair) -> Optional[RepairReserveLedger]:
    return _sync_ledger_entry(
        db,
        source_type="repair",
        source_id=repair.id,
        entry_type="withdrawal",
        truck_id=repair.truck_id,
        entry_date=repair.repair_date,
        amount=repair.cost,
        description_fn=lambda: format_withdrawal_description(repair),
        should_write=True,
    )


def delete_reserve_ledger_entry(db: Session, *, source_type: str, source_id: int) -> int:
    deleted = (
        db.query(RepairReserveLedger)
        .filter(RepairReserveLedger.source_type == source_type, RepairReserveLedger.source_id == source_id)
        .delete(synchronize_session=False)
    )
    return deleted
