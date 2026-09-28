from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace
from app.services.investment_progress import income_sources, settlement_progress
from app.models.truck import Truck
from app.models.settlement import Settlement
from tests.test_finance import truck


def asset(funding='heloc'):
    return SimpleNamespace(investment_plans=[dict(funding=funding,start='2026-01-01',effective='2026-01-01',months=60,
        acquisition_cost='75000',initial_cash='75000' if funding=='cash' else '0',financed='0' if funding=='cash' else '75000',
        annual_rate='0' if funding=='cash' else '.065',net_resale='40000',monthly_allocation='1600',balance_at_sale='0' if funding=='cash' else '40000')])


def row(i, amount, day):
    return dict(id=i, amount=D(amount), date=date(2026,1,day),kind='Truck allocation')


def test_settlement_income_drives_payment_projection_not_full_1600_assumption():
    r=settlement_progress(asset(),[row(1,'400',7),row(2,'400',14)],date(2026,1,31))
    assert r['allocated_income']=='800.00'
    assert r['loan_allocation']=='450.74'
    assert D(r['projected_balance'])==D('75000')+D(r['modeled_interest'])-D(r['loan_allocation'])
    assert r['actual_balance'] is None
    assert r['target_date'] > '2031-01-01'  # reduced earnings push payoff beyond the baseline
    assert sum(D(x['loan_allocation']) for x in r['sources'])==D(r['loan_allocation'])


def test_cash_progress_reconciles_to_cent_and_keeps_sale_recovery_separate():
    r=settlement_progress(asset('cash'),[row(1,'1600',7),row(2,'400',14)],date(2026,1,31))
    assert r['loan_allocation']=='0.00'
    assert r['cash_recovery']=='729.16'
    assert D(r['cash_recovery'])+D(r['cash_recovery_remaining'])==D('35000')
    assert D(r['allocated_income'])==D(r['cash_recovery'])+D(r['remaining_after_allocations'])


def test_missing_income_accrues_interest_without_fabricated_payment():
    r=settlement_progress(asset(),[],date(2026,1,31))
    assert r['loan_allocation']=='0.00'
    assert D(r['projected_balance'])>75000
    assert r['target_date'] is None


def test_source_parent_and_child_count_once_rental_and_tenant_boundaries(db,truck):
    trailer=Truck(tenant_id=1,name='Trailer',vehicle_type='trailer');db.add(trailer);db.flush()
    parent=Settlement(truck_id=truck.id,settlement_date=date(2026,1,7),trailer_income_split_trailer_id=trailer.id,trailer_income_split_amount=400,gross_revenue=3000)
    db.add(parent);db.flush()
    db.add_all([Settlement(truck_id=trailer.id,settlement_date=date(2026,1,7),source_settlement_id=parent.id,gross_revenue=400),Settlement(truck_id=trailer.id,settlement_date=date(2026,1,14),gross_revenue=1600)])
    db.commit()
    rows=income_sources(db,1,trailer,date(2026,1,1),date(2026,1,31))
    assert len(rows)==2
    assert sum(r['amount'] for r in rows)==2000
    assert income_sources(db,2,trailer,date(2026,1,1),date(2026,1,31))==[]
    assert len(income_sources(db,1,trailer,date(2026,1,8),date(2026,1,31)))==1


def test_rate_revision_applies_only_after_effective_date():
    a=asset();baseline=settlement_progress(a,[],date(2026,1,10))
    a.investment_plans.append({**a.investment_plans[0], 'effective':'2026-01-15','annual_rate':'.1'})
    assert settlement_progress(a,[],date(2026,1,10))==baseline
    assert D(settlement_progress(a,[],date(2026,1,31))['modeled_interest'])>D(settlement_progress(asset(),[],date(2026,1,31))['modeled_interest'])


def test_changed_borrowing_requires_financing_adjustment():
    a=asset();a.investment_plans.append({**a.investment_plans[0], 'effective':'2026-01-15','financed':'74000','initial_cash':'1000'})
    assert 'unavailable' in settlement_progress(a,[],date(2026,1,31))


def test_progress_endpoint_uses_tenant_scope(client, db, tenant_headers):
    from app.models.tenant import Tenant
    db.add(Tenant(id=2,name='Other',business_type='logistics'));db.flush()
    t=Truck(tenant_id=2,name='Private trailer',vehicle_type='trailer',investment_plans=asset().investment_plans)
    db.add(t);db.commit()
    assert client.get(f'/api/trucks/{t.id}/investment-progress?as_of=2026-01-31',headers=tenant_headers).status_code==404


def test_dealer_income_allocates_quoted_payment_without_second_principal_reserve():
    a=SimpleNamespace(investment_plans=[dict(funding='dealer',start='2026-01-01',effective='2026-01-01',months=60,acquisition_cost='73099',initial_cash='14619.80',financed='58979.20',annual_rate='.1125',net_resale='40000',monthly_allocation='1600',balance_at_sale='0',financed_fees='500',quoted_monthly_payment='1295')])
    r=settlement_progress(a,[row(1,'1600',31)],date(2026,1,31))
    assert r['loan_allocation']=='1295.00'
    assert r['cash_recovery']=='0.00'
    assert r['remaining_after_allocations']=='305.00'
    assert D(r['projected_balance'])==D('58979.20')+D(r['modeled_interest'])-D('1295')


def test_weekly_targets_use_finance_calendar_proration():
    from app.services.trailer_investment import plan_day_targets
    a=asset()
    r=settlement_progress(a,[],date(2026,2,2))
    assert r['week_start']=='2026-01-26'
    assert r['week_end']=='2026-02-01'
    from datetime import timedelta
    targets=[plan_day_targets(a.investment_plans[0],date(2026,1,26)+timedelta(days=i)) for i in range(7)]
    assert D(r['weekly_loan_target'])==sum(t[1] for t in targets)
    assert D(r['weekly_cash_target'])==sum(t[0] for t in targets)
    assert r['original_borrowed']=='75000.00'
    assert r['initial_cash']=='0.00'
