from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from app.services.settlement_history import review_rows


def sample(i=1, day='2026-09-21', fuel='100.00', miles='700'):
    r={'id':i,'truck_id':1,'name':'603','settlement_date':day,'source_settlement_id':None,'settlement_type':'Carrier A','expense_categories':{'driver_pay':'300.00','fuel':fuel},'overview_amounts':{'gross_before_dispatch':'1000.00','dispatch_fee':'100.00'},'cash_settlement_amount':str(Decimal('600')-Decimal(fuel)),'miles_driven':miles,'net_profit':str(Decimal('600')-Decimal(fuel))}
    p={'source_ref':str(i),'freight_gross':'1000.00','carrier_retention':'100.00','deductions':r['expense_categories'],'reported_payout':r['cash_settlement_amount'],'miles':miles,'mileage_basis':'reported','fuel':[{'date':day,'gallons':'20','amount':fuel,'product':'unknown','location':'A'}],'loads':[{'load_id':str(i),'delivery':day,'pickup':day,'freight_gross':'1000.00','loaded_miles':miles,'empty_miles':'0'}]}
    return r,{'id':str(i),'sha256':str(i),'proposal':p}


def test_full_reconciliation_excludes_internal_allocations_and_guards_mpg():
    r,s=sample();r['repair_reserve_amount']='300.00';r['trailer_income_split_amount']='400.00'
    derived={**r,'id':2,'source_settlement_id':1}
    rows=review_rows([r,derived],{1:s})
    assert len(rows)==1
    assert rows[0]['difference']=='0.00'
    assert rows[0]['calculated_remainder']=='500.00'
    assert rows[0]['measured_mpg'] is None
    assert rows[0]['gallons_purchased']=='20.00'
    assert rows[0]['status']=='arithmetic_matched'
    s['proposal']['mileage_basis']='estimated'
    result=review_rows([r],{1:s})[0]
    assert result['fuel_per_mile'] is None and result['miles'] is None


def test_missing_original_and_unmapped_pdf_never_verify_stored_figures():
    r,s=sample()
    assert review_rows([r],{})[0]['status']=='missing_source'
    s.pop('proposal')
    result=review_rows([r],{1:s})[0]
    assert result['status']=='needs_review' and result['difference'] is None
    assert result['fuel_per_mile'] is None


def test_payout_discrepancy_and_date_review_preserve_inputs():
    r,s=sample();s['proposal']['reported_payout']='499.00';s['proposal']['loads'][0]['delivery']='2026-09-23'
    original=deepcopy(r)
    result=review_rows([r],{1:s})[0]
    assert result['difference']=='-1.00' and result['status']=='needs_review'
    assert {'payout_difference','service_date','stored_difference'} <= {x['code'] for x in result['issues']}
    assert r==original


def test_rolling_fuel_spending_weighted_windows_and_carrier_isolation():
    records=[];sources={}
    for i in range(8):
        r,s=sample(i+1,(date(2026,7,1)+timedelta(days=i*7)).isoformat(),fuel='200.00' if i>=4 else '100.00')
        records.append(r);sources[r['id']]=s
    rows=review_rows(records,sources)
    assert any(x['code']=='fuel_spending' for x in rows[0]['issues'])
    assert rows[0]['measured_mpg'] is None
    records[-1]['settlement_type']='New carrier'
    assert not any(x['code']=='fuel_spending' for x in review_rows(records,sources)[0]['issues'])


def test_history_route_enforces_business_authority(client,monkeypatch):
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS','1')
    monkeypatch.setenv('APP_AUTH_TENANT_IDS','1')
    assert client.get('/api/v1/accounting/settlement-history',headers={'X-Tenant-ID':'1'}).status_code==200
    assert client.get('/api/v1/accounting/settlement-history',headers={'X-Tenant-ID':'2'}).status_code==404
    assert client.get('/api/v1/accounting/settlement-history',headers={'X-Tenant-ID':'1'},params={'tenant_id':2}).status_code==400


def test_shared_original_and_repeated_loads_withheld_from_trends():
    r,s=sample();other,os=sample(2,'2026-09-22');os['sha256']=s['sha256']
    rows=review_rows([r,other],{1:s,2:os})
    assert all(r['status']=='needs_review' and r['fuel_per_mile'] is None for r in rows)
    os['sha256']='different';os['proposal']['loads'][0]['load_id']='1'
    assert all(r['status']=='needs_review' for r in review_rows([r,other],{1:s,2:os}))


def test_load_mileage_mismatch_withholds_per_mile_results():
    r,s=sample();s['proposal']['loads'][0]['loaded_miles']='600'
    row=review_rows([r],{1:s})[0]
    assert row['miles'] is None and row['fuel_per_mile'] is None
    assert 'mileage_total' in [i['code'] for i in row['issues']]


def test_277_mapping_negative_payout_and_unknown_distance():
    from app.services.settlement_evidence import normalize_277_review
    text="""277 Logistics
Pay Period: 03/07/2026
Pay Amount Driver's pay
B-ABC1 Driver truck 02/28/2026 03/02/2026 03/07/2026 $1,827.50 $600.00
Gross Pay $1,827.50
Dispatch Fee $146.20
Driver's Pay $600.00
Driver's Pay Fee $39.00
Fuel $650.00
IFTA $50.00
Safety $20.00
Prepass $70.00
Insurance $350.00
Reimbursment $0.00
Bonus $0.00
Deductions $0.00
Net Pay -$97.70"""
    p=normalize_277_review(text)
    assert p['reported_payout']=='-97.70' and p['miles'] is None and not p['fuel']
    r,s=sample();r['settlement_date']='2026-03-07';s['proposal']=p
    row=review_rows([r],{1:s})[0]
    assert row['difference']=='0.00' and row['status']=='arithmetic_matched'
    assert row['measured_mpg'] is None and row['fuel_per_mile'] is None
    assert normalize_277_review(text+'\nGross Pay $1.00') is None


def test_owner_comparison_explains_exact_gap_and_flags_partial_period():
    from app.services.fleet_insights import owner_insights
    a={'date':'2026-09-21','period_start':'2026-09-14','period_end':'2026-09-21','source_ref':'A','evidence_id':'a','legacy_id':1,'freight_gross':'11800.00','carrier_retention':'1416.00','deductions':{'driver_pay':'3540.00','fuel':'2811.94','insurance':'300.00','tolls':'54.72'},'reported_payout':'3677.34','miles':'3114','mileage_basis':'reported','fuel':[],'loads':[]}
    b={**a,'source_ref':'B','evidence_id':'b','legacy_id':2,'freight_gross':'11900.00','carrier_retention':'1428.00','deductions':{'driver_pay':'3570.00','fuel':'4032.89','insurance':'300.00','tolls':'209.53','support':'200.00'},'reported_payout':'2159.58','miles':'3665'}
    report={'pairs':[{'truck_id':i,'name':name,'trailer_ids':[],'settlements':[s],'earnings':s['reported_payout']} for i,name,s in [(1,'603',a),(2,'609',b)]],'period':{'calendar_days':7},'legacy_comparison':{'rows':[{'legacy_id':i} for i in [1,2,3]]}}
    result=owner_insights(report)
    assert result['comparisons'][0]['difference']=='-1517.76'
    assert sum(Decimal(e['amount']) for e in result['comparisons'][0]['effects'])==Decimal('-1517.76')
    assert result['comparisons'][0]['fuel_rate_change_percent']=='21.86'
    assert result['unposted_in_period']==1


def test_other_expense_spike_is_an_investigation_not_loss():
    rows=[];sources={}
    for i in range(5):
        r,s=sample(i+1,(date(2026,7,1)+timedelta(days=i*7)).isoformat())
        if i==4:
            s['proposal']['deductions']['support']='200.00';s['proposal']['reported_payout']='300.00'
        rows.append(r);sources[r['id']]=s
    issue=next(i for i in review_rows(rows,sources)[0]['issues'] if i['code']=='expense_spike')
    assert issue['amount']=='200.00' and 'valid one-time cost' in issue['detail']


def test_legacy_float_dust_does_not_create_a_money_discrepancy():
    r,s=sample();r['expense_categories']={**r['expense_categories'],'driver_pay':300.00000000001}
    assert not review_rows([r],{1:s})[0]['differences']
