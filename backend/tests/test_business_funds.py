from datetime import date
from decimal import Decimal
from app.services.business_funds import movement, business_funds
from tests.test_finance import truck
from app.models.settlement import Settlement
from app.models.repair import Repair


def test_movement_preserves_shortfall_and_period_reconciliation():
    result = movement([(date(2026, 1, 1), Decimal('300')), (date(2026, 2, 1), Decimal('300')), (date(2026, 2, 2), Decimal('-800'))], date(2026, 2, 1), date(2026, 2, 28))
    assert result == {'opening': '300.00', 'added': '300.00', 'used': '800.00', 'balance': '-200.00'}


def test_business_funds_uses_records_without_bank_confirmation(db, truck):
    original = Settlement(truck_id=truck.id, settlement_date=date(2026, 9, 21), repair_reserve_amount=Decimal('300'))
    db.add(original)
    db.flush()
    db.add(Settlement(truck_id=truck.id, settlement_date=date(2026, 9, 22), repair_reserve_amount=Decimal('300'), source_settlement_id=original.id))
    db.add(Repair(truck_id=truck.id, repair_date=date(2026, 9, 22), cost=Decimal('100'), paid_from_reserve=True))
    db.add(Repair(truck_id=truck.id, repair_date=date(2026, 9, 23), cost=Decimal('999'), paid_from_reserve=False))
    db.flush()
    result = business_funds(db, truck.tenant_id, date(2026, 9, 21), date(2026, 9, 27))
    assert result['repair'] == {'opening':'0.00','added':'300.00','used':'100.00','balance':'200.00'}
    assert business_funds(db, 999, date(2026, 9, 21), date(2026, 9, 27))['repair']['balance'] == '0.00'


def test_recovery_history_counts_original_and_rental_once(db, truck):
    from tests.test_investment_progress import asset
    from app.models.truck import Truck
    trailer = Truck(tenant_id=truck.tenant_id, name='Cash trailer', vehicle_type='trailer', investment_plans=asset('cash').investment_plans)
    db.add(trailer)
    db.flush()
    parent = Settlement(truck_id=truck.id, settlement_date=date(2026, 1, 7), trailer_income_split_trailer_id=trailer.id, trailer_income_split_amount=400)
    db.add(parent)
    db.flush()
    db.add(Settlement(truck_id=trailer.id, settlement_date=date(2026, 1, 7), source_settlement_id=parent.id, gross_revenue=400))
    db.add(Settlement(truck_id=trailer.id, settlement_date=date(2026, 1, 14), gross_revenue=1600))
    db.flush()
    funds = business_funds(db, truck.tenant_id, date(2026, 1, 10), date(2026, 1, 31))
    assert funds['capital']['opening'] == '145.83'
    assert funds['capital']['added'] == '583.33'
    assert funds['capital']['balance'] == '729.16'
