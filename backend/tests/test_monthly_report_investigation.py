"""Regression coverage for settlement remaining, incurred costs and reserve payments."""
from datetime import date
from decimal import Decimal
from app.models.truck import Truck
from app.models.settlement import Settlement
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.routers.analytics import _get_time_series_impl
from app.routers.repair_reserves import get_reserve_balances
from app.services.business_funds import repair_fund
from app.routers.settlements import apply_repair_reserve_to_source


def test_monthly_result_retains_reserve_deduction_then_subtracts_incurred_cost(db):
    truck = Truck(tenant_id=1, name='Investigation', vehicle_type='truck')
    db.add(truck); db.flush()
    values = dict(gross_revenue=2000, expenses=500, net_profit=1500)
    apply_repair_reserve_to_source(values, 400)
    db.add(Settlement(truck_id=truck.id, settlement_date=date(2026,10,11),
        week_start=date(2026,10,4), repair_reserve_amount=400, **values))
    db.add(Repair(truck_id=truck.id, repair_date=date(2026,10,12),
        cost=300, description='Unpaid incurred repair', paid_from_reserve=False))
    db.flush()
    data = _get_time_series_impl('week_start',None,'truck',False,db,1)
    october = next(row for row in data['by_month'] if row['month_key']=='2026-10')
    assert october['settlement_remainder'] == 1100
    assert october['net_profit'] == 800  # 1500 - 400 earmark - 300 cost
    assert october['repair_reserve_amount'] == 400
    assert october['repairs'] == 300
    assert data['by_week'][0]['net_profit'] == 1100
    assert repair_fund(db,1,date(2026,10,1),date(2026,10,31))['balance'] == '400.00'


def test_27th_and_28th_group_differently_despite_same_payment_date(db):
    ids=[]
    for start in (27,28):
        truck=Truck(tenant_id=1,name=f'Truck {start}',vehicle_type='truck')
        db.add(truck); db.flush()
        row=Settlement(truck_id=truck.id,settlement_date=date(2026,10,4),
            week_start=date(2026,9,start),gross_revenue=1600,expenses=500,
            net_profit=1100,repair_reserve_amount=400)
        db.add(row); db.flush(); ids.append(row.id)
    data=_get_time_series_impl('week_start',None,'truck',False,db,1)
    months={row['month_key']:row for row in data['by_month']}
    assert [s['settlement_id'] for s in months['2026-09']['settlements']] == [ids[0]]
    assert [s['settlement_id'] for s in months['2026-10']['settlements']] == [ids[1]]
    assert months['2026-10']['repair_reserve_amount'] == 400
    assert repair_fund(db,1,date(2026,10,1),date(2026,10,31))['added'] == '800.00'


def test_running_balance_includes_later_entries_but_asof_fund_does_not(db):
    truck=Truck(tenant_id=1,name='Pool',vehicle_type='truck')
    db.add(truck); db.flush()
    for day, amount in [(date(2026,9,1),Decimal('400')),(date(2026,10,1),Decimal('600'))]:
        db.add(Settlement(truck_id=truck.id,settlement_date=day,repair_reserve_amount=amount))
        db.add(RepairReserveLedger(tenant_id=1,truck_id=truck.id,entry_date=day,
            entry_type='deposit',amount=amount,source_type='settlement',source_id=day.month))
    db.flush()
    assert get_reserve_balances(db,1)[0]['balance'] == Decimal('1000')
    assert repair_fund(db,1,date(2026,9,1),date(2026,9,30))['balance'] == '400.00'


def test_october_remaining_does_not_double_charge_reserve_repairs(db):
    truck = Truck(tenant_id=1, name='October', vehicle_type='truck')
    db.add(truck); db.flush()
    db.add(Settlement(truck_id=truck.id, settlement_date=date(2026,10,26),
        week_start=date(2026,10,19), gross_revenue=52296, expenses=44817.22,
        net_profit=7478.78, repair_reserve_amount=3200, expense_categories={"fleet_manager_support":400}))
    db.add(Repair(truck_id=truck.id, repair_date=date(2026,10,20),
        cost=8056.76, description='October invoices', paid_from_reserve=True))
    db.flush()
    data = _get_time_series_impl('week_start',None,'truck',False,db,1)
    month = data['by_month'][0]
    assert month['settlement_remainder'] == 7478.78
    assert round(month['settlement_remainder'] + 2878.68, 2) == 10357.46
    assert month['net_profit'] == -577.98
    assert month['repairs'] == 8056.76
    assert month['fleet_manager_support'] == 400
    assert data['by_year'][0]['settlement_remainder'] == 7478.78


def test_partial_payment_changes_shared_reserve_not_settlement_remaining(db):
    truck = Truck(tenant_id=1, name='Partial', vehicle_type='truck')
    db.add(truck); db.flush()
    db.add(Settlement(truck_id=truck.id, settlement_date=date(2026,10,5),
        week_start=date(2026,10,1), net_profit=1100, repair_reserve_amount=400))
    db.add(Repair(truck_id=truck.id, repair_date=date(2026,10,12),
        cost=1000, description='Invoice, not evidence of cash paid', paid_from_reserve=False))
    db.add(RepairReserveLedger(tenant_id=1,truck_id=truck.id,entry_date=date(2026,10,5),
        entry_type='deposit',amount=400,source_type='settlement',source_id=1))
    db.flush()
    for payment, expected in [(0,400),(200,200),(500,-300)]:
        if payment:
            db.add(RepairReserveLedger(tenant_id=1,truck_id=truck.id,entry_date=date(2026,10,20),
                entry_type='withdrawal',amount=payment,source_type='dbn_payment',source_id=payment))
            db.flush()
        data = _get_time_series_impl('week_start',None,'truck',False,db,1)
        assert data['by_month'][0]['settlement_remainder'] == 1100
        assert data['by_month'][0]['repairs'] == 1000
        assert get_reserve_balances(db,1)[0]['balance'] == Decimal(expected)


def test_signed_expense_categories_reconcile_to_authoritative_total(db):
    from app.routers.analytics import _get_dashboard_impl
    truck=Truck(tenant_id=1,name='Credit',vehicle_type='truck')
    db.add(truck);db.flush()
    db.add(Settlement(truck_id=truck.id,settlement_date=date(2026,10,5),
        week_start=date(2026,9,28),gross_revenue=1000,expenses=200,net_profit=800,
        expense_categories={'fuel':300,'custom':-100}))
    db.flush()
    series=_get_time_series_impl('week_start',None,'truck',False,db,1)
    for periods in ['by_week','by_month','by_year']:
        row=series[periods][0]
        assert row['fuel']==300
        assert row['custom']==-100
        assert row['fuel']+row['custom']==row['expenses']==200
        assert row['settlement_remainder']==800
    categories=_get_dashboard_impl(None,'truck',db,1)['trucks']['expense_categories']
    assert categories['custom']==-100
