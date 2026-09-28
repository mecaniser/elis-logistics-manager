from dataclasses import replace
from decimal import Decimal as D
import pytest
from app.services.trailer_investment import TrailerInvestment, investment_projection


def cash():
    return TrailerInvestment('cash', D('75000'), D('75000'), D('0'), D('0'), 60, D('40000'), D('1600'))


def test_cash_recovers_purchase_once_including_sale():
    r = investment_projection(cash())
    assert r['monthly_cash_recovery'] == '583.33'
    assert r['monthly_left'] == '1016.67'
    assert r['protected_cash_recovery'] == '35000.00'
    assert r['projected_profit'] == '61000.00'
    assert r['cash_roi_percent'] == '81.33'
    assert r['terminal_above_investment'] == '0.00'


def test_heloc_sale_clears_debt_without_duplicate_reserve():
    r = investment_projection(TrailerInvestment('heloc', D('75000'), D('0'), D('75000'), D('.065'), 60, D('40000'), D('1600'), D('40000')))
    assert r['monthly_payment'] == '901.48'
    assert r['monthly_left'] == '698.52'
    assert r['sale_equity'] == '0.00'
    assert r['monthly_cash_recovery'] == '0.00'
    assert r['principal_repaid'] == '35000.00'
    assert r['cash_roi_percent'] is None
    assert D(r['projected_profit']) + D(r['financing_cost']) == D('61000')


def test_dealer_quote_exposes_rate_discrepancy_without_extra_recovery():
    r = investment_projection(TrailerInvestment('dealer', D('73099'), D('14619.80'), D('58979.20'), D('.1125'), 60, D('40000'), D('1600'), financed_fees=D('500'), quoted_monthly_payment=D('1295')))
    assert r['monthly_left'] == '305.00'
    assert r['operating_surplus'] == '18300.00'
    assert r['terminal_above_investment'] == '25380.20'
    assert r['projected_profit'] == '43680.20'
    assert r['monthly_cash_recovery'] == '0.00'
    assert r['rate_based_monthly_payment'] == '1289.72'
    assert r['quote_payment_difference'] == '5.28'


def test_zero_interest_and_underwater_sale():
    r = investment_projection(TrailerInvestment('heloc', D('75000'), D('0'), D('75000'), D('0'), 60, D('30000'), D('1600'), D('40000')))
    assert r['monthly_payment'] == '583.33'
    assert r['sale_equity'] == '-10000.00'
    assert r['protected_cash_recovery'] == '10000.00'
    assert r['projected_profit'] == '51000.00'


@pytest.mark.parametrize('changes', [dict(months=0), dict(net_resale=D('NaN')), dict(financed=D('1')), dict(monthly_allocation=D('-1')), dict(funding='unknown')])
def test_invalid_inputs(changes):
    with pytest.raises(ValueError):
        investment_projection(replace(cash(), **changes))


def test_low_earnings_preserve_losses():
    r = investment_projection(replace(cash(), monthly_allocation=D('100')))
    assert r['monthly_left'] == '-483.33'
    assert r['projected_profit'] == '-29000.00'


def test_monthly_allocation_not_four_week_assumption():
    from datetime import date
    from app.services.trailer_investment import monthly_day_amount
    assert sum(monthly_day_amount(D('1600'), date(2026, 9, day)) for day in range(1, 31)) == D('1600')


def test_plan_api_preserves_revisions_and_tenant_scope(client, db, tenant_headers):
    from app.models.truck import Truck
    t = Truck(tenant_id=1, name='Investment trailer', vehicle_type='trailer', total_cost=D('75000'))
    other = Truck(tenant_id=2, name='Other investment', vehicle_type='trailer')
    db.add_all([t, other]); db.commit()
    payload = dict(funding='cash', start='2025-09-15', effective='2026-09-28', months=60,
                   acquisition_cost='75000', initial_cash='75000', financed='0', annual_rate='0',
                   net_resale='40000', monthly_allocation='1600')
    assert client.post(f'/api/trucks/{other.id}/investment-plan', json=payload, headers=tenant_headers).status_code == 404
    count = db.query(Truck).count()
    assert client.post('/api/trucks/investment-preview', json=payload, headers=tenant_headers).status_code == 200
    assert db.query(Truck).count() == count
    r = client.post(f'/api/trucks/{t.id}/investment-plan', json=payload, headers=tenant_headers)
    assert r.status_code == 200, r.text
    assert r.json()['projection']['projected_profit'] == '61000.00'
    assert client.post(f'/api/trucks/{t.id}/investment-plan', json=payload, headers=tenant_headers).status_code == 200
    assert client.post(f'/api/trucks/{t.id}/investment-plan', json={**payload,'months':36,'effective':'2026-09-27'}, headers=tenant_headers).status_code == 409
    assert client.post(f'/api/trucks/{t.id}/investment-plan', json={**payload,'effective':'2026-10-01','months':36}, headers=tenant_headers).status_code == 200
    db.refresh(t)
    assert len(t.investment_plans) == 2
    assert t.investment_plans[0]['months'] == 60


def test_additive_migration_is_repeatable():
    from sqlalchemy import create_engine, text, inspect
    from app.migration_runner import _add_investment_plans
    engine = create_engine('sqlite://')
    with engine.begin() as c:
        c.execute(text('CREATE TABLE trucks (id INTEGER PRIMARY KEY, name TEXT)'))
        c.execute(text("INSERT INTO trucks VALUES (1, 'Preserved')"))
    _add_investment_plans(engine); _add_investment_plans(engine)
    assert 'investment_plans' in {x['name'] for x in inspect(engine).get_columns('trucks')}
    with engine.connect() as c:
        assert c.execute(text('SELECT name FROM trucks')).scalar() == 'Preserved'
