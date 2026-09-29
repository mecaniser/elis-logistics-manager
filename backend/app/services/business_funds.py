"""Management fund balances from business records, independent of bank matching."""
from datetime import date
from app.models.truck import Truck
from app.models.settlement import Settlement
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.services.investment_progress import income_sources, settlement_progress
from app.services.finance import D, ZERO, money


def movement(entries, start, end):
    opening = sum((amount for day, amount in entries if day < start), ZERO)
    added = sum((amount for day, amount in entries if start <= day <= end and amount > 0), ZERO)
    used = -sum((amount for day, amount in entries if start <= day <= end and amount < 0), ZERO)
    return {key: money(value) for key, value in dict(opening=opening, added=added, used=used, balance=opening + added - used).items()}


def business_funds(db, tenant, start, end):
    assets = db.query(Truck).filter_by(tenant_id=tenant).all()
    ids = [a.id for a in assets]
    regime = date(2026, 1, 1)
    settlements = db.query(Settlement).filter(Settlement.truck_id.in_(ids), Settlement.source_settlement_id.is_(None), Settlement.settlement_date >= regime, Settlement.settlement_date <= end).all()
    repairs = db.query(Repair).filter(Repair.truck_id.in_(ids), Repair.paid_from_reserve.is_(True), Repair.repair_date >= regime, Repair.repair_date <= end).all()
    # Derive source entries directly; synced ledger deposits/withdrawals are copies.
    adjustments = db.query(RepairReserveLedger).filter_by(tenant_id=tenant, entry_type='adjustment').filter(RepairReserveLedger.truck_id.in_(ids), RepairReserveLedger.entry_date >= regime, RepairReserveLedger.entry_date <= end).all()
    repair_entries = [(s.settlement_date, D(s.repair_reserve_amount)) for s in settlements]
    repair_entries += [(r.repair_date, -D(r.cost)) for r in repairs]
    repair_entries += [(a.entry_date, D(a.amount)) for a in adjustments]
    capital_entries = []
    equipment = []
    for asset in assets:
        if not asset.investment_plans:
            continue
        since = date.fromisoformat(min(p['effective'] for p in asset.investment_plans))
        if since > end:
            continue
        progress = settlement_progress(asset, income_sources(db, tenant, asset, since, end), end)
        if not progress or progress.get('unavailable'):
            equipment.append({'asset_id': asset.id, 'name': asset.name, 'unavailable': (progress or {}).get('unavailable', 'Recovery plan unavailable')})
            continue
        entries = [(date.fromisoformat(s['date']), D(s['cash_recovery'])) for s in progress['sources']]
        capital_entries += entries
        equipment.append({'asset_id': asset.id, 'name': asset.name, **movement(entries, start, end)})
    return {'start': start.isoformat(), 'end': end.isoformat(), 'repair_since': regime.isoformat(),
            'repair': movement(repair_entries, start, end), 'capital': movement(capital_entries, start, end),
            'equipment': equipment,
            'basis': 'Settlement records and saved recovery plans. Repair spending follows repairs marked paid from reserve. Capital shows cumulative recovery before owner withdrawals; it is not a bank balance.'}
