from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from app.services.earnings_plan import period_target, saved_plan, earnings_plan
from tests.test_finance import truck, cmd, policy_setup, ASOF
from tests.test_retention import settlement
from app.services import finance as f


def test_calendar_targets_are_additive_to_cent():
    rate = Decimal('22129.69') / 156
    daily = sum(period_target(rate, date(2026, 9, day), date(2026, 9, day)) for day in range(1, 31))
    assert daily == period_target(rate, date(2026, 9, 1), date(2026, 9, 30))
    assert period_target(Decimal('300'), date(2026, 9, 21), date(2026, 9, 27)) == Decimal('300')


def test_saved_settings_keep_unknowns_and_zero_distinct():
    v = SimpleNamespace(purchase_date=None, id=1, name='trailer', vin='123', total_cost=Decimal('72129.69'), expected_resale_value=Decimal('50000'), planned_service_weeks=156, trailer_depreciation_reserve_amount=None, cash_investment=Decimal('1000'), default_repair_reserve_amount=None, loan_amount=Decimal('68099'), interest_rate=Decimal('.065'))
    p = saved_plan(v)
    assert p['capital_weekly'] == '141.86'
    assert p['capital_target'] == '22129.69'
    v.expected_resale_value = None
    assert saved_plan(v)['capital_weekly'] is None
    v.expected_resale_value = v.total_cost
    assert saved_plan(v)['capital_weekly'] == '0.00'


def test_report_reuses_saved_repair_target_without_posting(db, truck):
    truck.default_repair_reserve_amount = Decimal('300')
    db.commit()
    d = policy_setup(db)
    settlement(db, d, truck)
    before = len(f.state(db, 1, ASOF)['events'])
    report = f.report(db, 1, ASOF, date(2026, 9, 27), date(2026, 9, 27))
    row = report['earnings_plan']['pairs'][0]
    assert row['repair_target'] == '300.00'
    assert row['planning_subtotal'] == '2700.00'
    assert len(f.state(db, 1, ASOF)['events']) == before
    assert report['owner_cash']['protected_reserves'] == '0.00'


def test_unposted_history_included_once_and_other_tenant_excluded(db, truck):
    from app.models.settlement import Settlement
    truck.default_repair_reserve_amount = Decimal('300')
    db.add(Settlement(truck_id=truck.id, settlement_date=ASOF, gross_revenue=Decimal('1000'), expenses=Decimal('200'), net_profit=Decimal('800')))
    db.commit()
    r = f.report(db, 1, ASOF, date(2026,9,27), date(2026,9,27))
    p = r['earnings_plan']['pairs'][0]
    assert p['saved_remainder'] == '800.00'
    assert p['planning_subtotal'] == '500.00'
    assert len(p['saved_settlement_ids']) == 1
    # Once linked to posted history it must not be added a second time.
    r['pairs'][0]['settlements'] = [{'legacy_id': p['saved_settlement_ids'][0]}]
    assert earnings_plan(db, 1, r)['pairs'][0]['saved_remainder'] == '0.00'
    assert earnings_plan(db, 2, r)['pairs'] == []
