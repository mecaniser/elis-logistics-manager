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
    r['pairs'][0]['settlements'] = [{'id':'posted','date':str(ASOF),'deductions':{},'legacy_id': p['saved_settlement_ids'][0]}]
    assert earnings_plan(db, 1, r)['pairs'][0]['saved_remainder'] == '0.00'
    assert earnings_plan(db, 2, r)['pairs'] == []


def test_planning_pair_inference_is_dated_and_explicit_wins():
    from app.services.earnings_plan import planning_pair_days
    first, second = date(2026,9,21), date(2026,9,22)
    obs = [(1,3,first),(1,5,second)]
    pairs = planning_pair_days([],obs,first,second)
    assert pairs[(1,3)]['days'] == {first}
    assert pairs[(1,5)]['days'] == {second}
    assert pairs[(1,3)]['inferred']
    explicit = [{'truck_id':2,'trailer_id':3,'start':str(first),'end':str(second)}]
    assert (1,3) not in planning_pair_days(explicit,obs,first,second)
    assert (1,3) not in planning_pair_days([],[(1,3,first),(2,3,first)],first,second)


def test_planning_score_matches_bridge_and_preserves_recorded_score(db, truck):
    from tests.test_finance import bank, bill
    truck.default_repair_reserve_amount = Decimal('300')
    db.commit()
    d = policy_setup(db); bank(db); settlement(db, d, truck)
    cmd(db, 'reserve', pair_id=truck.id, purpose='repair', amount='100.00', note='Funded', evidence_id=d)
    b = bill(db, d, truck)
    cmd(db, 'payment', claim_id=b.id, amount='500.00', payer='owner', evidence_id=d)
    r = f.report(db, 1, ASOF, date(2026,9,27), date(2026,9,27))
    p = r['earnings_plan']['pairs'][0]
    score = r['earnings_plan']['retention']['pairs'][0]
    assert p['additional_protection'] == '200.00'
    assert score['retained'] == p['planning_subtotal'] == '2200.00'
    assert sum(Decimal(row['amount']) for row in score['bridge']) == Decimal('2200')
    assert score['retained_per_100'] == '22.00'
    assert score['score'] == '73.33'
    assert r['retention']['pairs'][0]['retained'] == '2400.00'


def test_planning_score_uses_matching_unposted_freight_and_excludes_linked_duplicates(db, truck):
    from app.models.settlement import Settlement
    truck.default_repair_reserve_amount = Decimal('300')
    db.add(Settlement(truck_id=truck.id, settlement_date=ASOF, gross_revenue=Decimal('1000'), expenses=Decimal('200'), net_profit=Decimal('800')))
    db.commit()
    r = f.report(db, 1, ASOF, date(2026,9,27), date(2026,9,27))
    score = r['earnings_plan']['retention']['pairs'][0]
    assert score['freight'] == '1000.00'
    assert score['retained_per_100'] == '50.00'
    assert score['score'] == '166.67'
    r['pairs'][0]['settlements'] = [{'id':'posted','date':str(ASOF),'deductions':{},'legacy_id': r['earnings_plan']['pairs'][0]['saved_settlement_ids'][0]}]
    score = earnings_plan(db, 1, r)['retention']['pairs'][0]
    assert score['freight'] == '0.00'
    assert score['score'] is None
    assert score['retained'] == '-300.00'


def test_internal_trailer_split_preserves_combined_total(db, truck):
    from app.models.settlement import Settlement
    from app.models.truck import Truck
    truck.default_repair_reserve_amount = Decimal('300')
    trailer = Truck(name='Trailer',tenant_id=1,vehicle_type='trailer',total_cost=Decimal('73231.09'),expected_resale_value=Decimal('50000'),planned_service_weeks=156)
    db.add(trailer); db.flush()
    db.add(Settlement(truck_id=truck.id,settlement_date=ASOF,gross_revenue=Decimal('1459.58'),expenses=Decimal('0'),net_profit=Decimal('1459.58'),repair_reserve_amount=Decimal('300'),trailer_income_split_trailer_id=trailer.id,trailer_income_split_amount=Decimal('400')))
    db.commit()
    r=f.report(db,1,ASOF,date(2026,9,27),date(2026,9,27))['earnings_plan']['pairs'][0]
    split=r['allocation_split']
    assert split['trailer_allocation']=='400.00'
    assert split['trailer_capital_target']=='148.92'
    assert split['trailer_contribution']=='251.08'
    assert split['truck_remainder']=='1459.58'
    assert Decimal(split['truck_remainder'])+Decimal(split['trailer_contribution'])+Decimal(split['pair_adjustments'])==Decimal(r['planning_subtotal'])
    from app.models.repair import Repair
    db.add(Repair(truck_id=truck.id,repair_date=ASOF,cost=Decimal('100'),paid_from_reserve=False)); db.commit()
    r=f.report(db,1,ASOF,date(2026,9,27),date(2026,9,27))['earnings_plan']['pairs'][0]
    assert r['allocation_split']['pair_adjustments']=='-100.00'
    assert r['planning_subtotal']=='1610.66'


def test_planning_freight_uses_only_included_sources_and_preserves_category_gap():
    from app.services.earnings_plan import planning_freight
    r={'revenue_breakdown':{'freight_gross':'11800.00','settlement_remainder':'3677.34','rows':[{'category':'carrier','amount':'1416.00'},{'category':'driver_pay','amount':'3540.00'},{'category':'fuel','amount':'2811.94'},{'category':'other','amount':'354.72'}]}, 'legacy_comparison':{'rows':[
        {'legacy_id':1,'freight_gross':'11900.00','settlement_remainder':'2159.58','carrier_retention':'1428.00','operating_deductions':'8312.42','deductions':{'driver_pay':'3570.00','fuel':'4032.89','support':'200.00','loan_interest':'20.00'}},
        {'legacy_id':2,'freight_gross':'11800.00'}]}}
    b=planning_freight(r,{1})
    assert b['freight_gross']=='23700.00'
    assert b['settlement_remainder']=='5836.92'
    assert b['saved_unposted_count']==1
    assert sum(Decimal(x['amount']) for x in b['rows'])+Decimal(b['settlement_remainder'])==Decimal(b['freight_gross'])
    assert next(x['amount'] for x in b['rows'] if x['category']=='unclassified_statement_adjustment')=='509.53'
    assert planning_freight(r,set())['freight_gross']=='11800.00'
