"""
Repair reserve ledger endpoints.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_tenant_id
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.models.truck import Truck

router = APIRouter()


def get_tenant_truck_or_404(db: Session, truck_id: int, tenant_id: int) -> Truck:
    truck = db.query(Truck).filter(Truck.id == truck_id, Truck.tenant_id == tenant_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    return truck


def _reserve_balance_query(db: Session, tenant_id: int):
    return (
        db.query(
            RepairReserveLedger.truck_id.label("truck_id"),
            func.sum(
                case((RepairReserveLedger.entry_type == "deposit", RepairReserveLedger.amount), else_=0)
            ).label("deposits_total"),
            func.sum(
                case((RepairReserveLedger.entry_type == "withdrawal", RepairReserveLedger.amount), else_=0)
            ).label("withdrawals_total"),
            func.sum(
                case((RepairReserveLedger.entry_type == "adjustment", RepairReserveLedger.amount), else_=0)
            ).label("adjustments_total"),
        )
        .filter(RepairReserveLedger.tenant_id == tenant_id)
        .group_by(RepairReserveLedger.truck_id)
    )


def _serialize_balance_row(row) -> dict:
    deposits_total = row.deposits_total or 0
    withdrawals_total = row.withdrawals_total or 0
    adjustments_total = row.adjustments_total or 0
    return {
        "truck_id": row.truck_id,
        "balance": deposits_total + adjustments_total - withdrawals_total,
        "deposits_total": deposits_total,
        "withdrawals_total": withdrawals_total,
        "adjustments_total": adjustments_total,
        "as_of": date.today(),
    }


@router.get("/trucks/{truck_id}/reserve-balance")
def get_reserve_balance(
    truck_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    get_tenant_truck_or_404(db, truck_id, tenant_id)
    row = _reserve_balance_query(db, tenant_id).filter(RepairReserveLedger.truck_id == truck_id).first()
    if not row:
        return {
            "truck_id": truck_id,
            "balance": 0,
            "deposits_total": 0,
            "withdrawals_total": 0,
            "adjustments_total": 0,
            "as_of": date.today(),
        }
    return _serialize_balance_row(row)


@router.get("/trucks/{truck_id}/reserve-ledger")
def get_reserve_ledger(
    truck_id: int,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    get_tenant_truck_or_404(db, truck_id, tenant_id)
    query = db.query(RepairReserveLedger).filter(
        RepairReserveLedger.tenant_id == tenant_id,
        RepairReserveLedger.truck_id == truck_id,
    )
    if from_date:
        query = query.filter(RepairReserveLedger.entry_date >= from_date)
    if to_date:
        query = query.filter(RepairReserveLedger.entry_date <= to_date)
    return query.order_by(RepairReserveLedger.entry_date.desc(), RepairReserveLedger.id.desc()).all()


@router.get("/reserve-balances")
def get_reserve_balances(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
):
    rows = _reserve_balance_query(db, tenant_id).all()
    return [_serialize_balance_row(row) for row in rows]
