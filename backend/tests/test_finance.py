import base64
import hashlib
from datetime import date
from uuid import uuid4
import pytest
from app.models.truck import Truck
from app.models.tenant import Tenant
from app.models.finance import FinanceEvidence, FinanceEvent, FinancePosting
from app.services import finance as f
from app.schemas.finance import Command

ASOF = date(2026, 9, 21)

@pytest.fixture(autouse=True)
def authority(monkeypatch):
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS', '1')
    monkeypatch.setenv('APP_AUTH_TENANT_IDS', '1')

@pytest.fixture
def truck(db):
    t = Truck(name='603', tenant_id=1, vehicle_type='truck'); db.add(t); db.commit(); return t

def doc(db, content=b'evidence'):
    e = FinanceEvidence(tenant_id=1, sha256=hashlib.sha256(content).hexdigest(), filename='source.csv', media_type='text/csv', content_base64=base64.b64encode(content).decode(), source_key=str(uuid4()), extraction_version='test', extracted={})
    db.add(e); db.commit(); return e.id

def cmd(db, kind, when='2026-09-21', key=None, **p):
    e = f.append_command(db, 1, Command(effective_date=when, payload={'kind': kind, **p}), key or str(uuid4())); db.commit(); return e

def policy_setup(db):
    d = doc(db)
    cmd(db, 'policy', when='2026-01-01', timezone='America/New_York', approved=True, account_coverage_confirmed=True, evidence_ids=[d])
    return d

def bank(db, rows='', opening='10000.00', closing='10000.00', typ='bank'):
    a = cmd(db, 'account', when='2026-01-01', name=typ, account_type=typ)
    m = cmd(db, 'csv_mapping', when='2026-01-01', name='CSV', date_column='Date', amount_column='Amount', description_column='Description', id_column='ID')
    d = doc(db, ('Date,Amount,Description,ID\n' + rows).encode())
    s = cmd(db, 'statement', account_id=a.id, mapping_id=m.id, evidence_id=d, start='2026-09-21', end='2026-09-21', opening=opening, closing=closing)
    return a, s

def bill(db, d, truck, **more):
    return cmd(db, 'bill', evidence_id=d, source_ref=str(uuid4()), description='Repair', amount='500.00', category='repairs', asset_id=truck.id, pair_id=truck.id, **more)

def test_september_acceptance_and_consistent_periods(db, truck):
    d = policy_setup(db)
    other = Truck(name='609', tenant_id=1, vehicle_type='truck'); db.add(other); db.commit()
    for t,g,c,driver,fuel,toll,support,net in [(truck,'11800.00','1416.00','3540.00','2811.94','54.72','0.00','3677.34'),(other,'11900.00','1428.00','3570.00','4032.89','209.53','200.00','2159.58')]:
        cmd(db,'settlement',evidence_id=d,source_ref=t.name,asset_id=t.id,period_start='2026-09-14',period_end='2026-09-21',freight_gross=g,carrier_retention=c,deductions={'driver_pay':driver,'fuel':fuel,'insurance':'300.00','tolls':toll,'support':support},reported_payout=net)
    r = f.report(db,1,date(2026,9,14),ASOF,ASOF)
    assert r['revenue_breakdown']['freight_gross']=='23700.00'
    assert r['revenue_breakdown']['settlement_remainder']=='5836.92'
    assert r['owner_cash']['available'] is None
    for start in [date(2026,9,14),date(2026,9,1),date(2026,1,1)]:
        assert f.ledger_report(db,1,start,ASOF)['income_statement']['net_income']=='5836.92'

def test_reserve_repair_no_double_deduction(db,truck):
    d=policy_setup(db); a,s=bank(db)
    r=cmd(db,'reserve',pair_id=truck.id,purpose='repair',amount='1000.00',opening=True,note='Confirmed allocation',evidence_id=d)
    b=bill(db,d,truck,reserve_id=r.id)
    assert f.cash_position(db,1,ASOF)['available']=='9000.00'
    m=next(e for e in f.events(db,1) if e.kind=='csv_mapping')
    source=doc(db,b'Date,Amount,Description,ID\n2026-09-22,-500.00,Repair,r1\n')
    s=cmd(db,'statement',when='2026-09-22',account_id=a.id,mapping_id=m.id,evidence_id=source,start='2026-09-22',end='2026-09-22',opening='10000.00',closing='9500.00')
    cmd(db,'payment',when='2026-09-22',claim_id=b.id,amount='500.00',payer='business',transaction_id=s.payload['_transactions'][0]['id'])
    cash=f.cash_position(db,1,date(2026,9,22))
    assert cash['available']=='9000.00'
    assert cash['protected_reserves']=='500.00'
    assert cash['uncovered_bills']=='0.00'

def test_owner_payment_and_personal_heloc_no_duplicate_claim(db,truck):
    d=policy_setup(db); bank(db); b=bill(db,d,truck)
    p=cmd(db,'payment',claim_id=b.id,amount='500.00',payer='owner',evidence_id=d)
    for action in ['draw','principal_payment']:
        cmd(db,'financing',action=action,facility='HELOC',amount='1000.00',business_amount='500.00',owner_claim_id=p.id,asset_id=truck.id,evidence_id=d,use_description='Business and personal use traced')
    cash=f.cash_position(db,1,ASOF)
    assert cash['uncovered_bills']=='0.00'
    assert cash['owner_reimbursement']=='500.00'
    assert cash['available']=='9500.00'
    assert f.ledger_report(db,1,date.min,ASOF)['income_statement']['net_income']=='-500.00'

def test_card_payment_and_repayment_one_expense(db,truck):
    d=policy_setup(db)
    a,bs=bank(db,rows='2026-09-21,-500.00,Card payment,b1\n',closing='9500.00')
    a,cs=bank(db,rows='2026-09-21,-500.00,Repair,c1\n2026-09-21,500.00,Payment,c2\n',opening='0.00',closing='0.00',typ='card')
    b=bill(db,d,truck)
    cmd(db,'payment',claim_id=b.id,amount='500.00',payer='card',transaction_id=cs.payload['_transactions'][0]['id'])
    cmd(db,'bank_match',transaction_id=bs.payload['_transactions'][0]['id'],match_type='card_repayment',operating_amount='500.00',counterpart_transaction_id=cs.payload['_transactions'][1]['id'])
    report=f.ledger_report(db,1,date.min,ASOF)
    assert report['income_statement']['net_income']=='-500.00'
    assert report['ledger_cards']=='0.00'
    assert f.cash_position(db,1,ASOF)['available']=='9500.00'

def test_idempotency_duplicate_sources_and_negative_cash(db,truck):
    d=policy_setup(db); bank(db,opening='100.00',closing='100.00')
    p=dict(evidence_id=d,source_ref='unique',description='Repair',amount='500.00',category='repairs',asset_id=truck.id)
    first=cmd(db,'bill',key='stable-key',**p)
    assert cmd(db,'bill',key='stable-key',**p).id==first.id
    for key,amount in [('stable-key','600.00'),('different-key','500.00')]:
        with pytest.raises(Exception): cmd(db,'bill',key=key,**{**p,'amount':amount})
        db.rollback()
    assert db.query(FinancePosting).count()==1
    assert f.cash_position(db,1,ASOF)['available']=='-400.00'

def test_estimated_mileage_cannot_measure_mpg(db,truck):
    d=doc(db)
    p=dict(asset_id=truck.id,start='2026-09-01',end='2026-09-21',miles='1000',basis='estimated',evidence_id=d)
    with pytest.raises(Exception): cmd(db,'travel',**p,consumed_gallons='200',consumption_supported=True)
    db.rollback();cmd(db,'travel',**p)
    assert f.fuel_performance(db,1,ASOF)[0]['measured_mpg'] is None

def test_disposal_and_capital(db,truck):
    d=policy_setup(db)
    cmd(db,'asset_plan',asset_id=truck.id,acquired='2025-01-01',acquisition_cost='50000.00',expected_resale='20000.00',planned_sale='2027-01-01',evidence_id=d)
    with pytest.raises(Exception):
        cmd(db,'disposal',asset_id=truck.id,gross_sale='20000.00',selling_costs='1000.00',book_accumulated_depreciation='30000.00',evidence_id=d)
    db.rollback()
    cmd(db,'journal',description='Opening equipment basis',evidence_id=d,lines=[{'account':'equipment','asset_id':truck.id,'debit':'50000.00'},{'account':'accumulated_depreciation','asset_id':truck.id,'credit':'30000.00'},{'account':'owner_equity','credit':'20000.00'}])
    cmd(db,'disposal',asset_id=truck.id,gross_sale='20000.00',selling_costs='1000.00',book_accumulated_depreciation='30000.00',financing_payoff='7000.00',evidence_id=d)
    r=f.capital_schedule(db,1,ASOF)[0]
    assert r['target']=='30000.00'
    assert r['realized_lifetime_profit']=='-31000.00'
    assert r['sale_cash_after_financing']=='12000.00'
    statement=f.ledger_report(db,1,date.min,ASOF)['income_statement']
    assert statement['operating_earnings']=='0.00'
    assert statement['disposal_gain']=='-1000.00'
    assert statement['net_income']=='-1000.00'

def test_authority_and_strict_money(client,db,tenant_headers):
    db.add(Tenant(id=2,name='Foreign'));db.commit()
    for url in ['/api/v1/accounting/context','/api/accounting/chart-of-accounts']:
        assert client.get(url,headers={'X-Tenant-ID':'2'}).status_code==404
    assert client.get('/api/v1/accounting/context').status_code==400
    assert client.get('/api/v1/accounting/context',headers=[('X-Tenant-ID','1'),('X-Tenant-ID','2')]).status_code==400
    r=client.post('/api/v1/accounting/events',headers={**tenant_headers,'Idempotency-Key':'test-key-1'},json={'effective_date':'2026-09-21','payload':{'kind':'reserve','pair_id':1,'purpose':'repair','amount':300.0,'evidence_id':'none','note':'test'}})
    assert r.status_code==422
    assert client.get('/api/accounting/export/trial-balance',headers=tenant_headers).status_code==409

def test_frozen_snapshots_and_blocked_package(client,db,tenant_headers):
    r=client.post('/api/v1/accounting/report-runs',headers=tenant_headers,json={'start':'2026-09-01','end':'2026-09-21','as_of':'2026-09-21'})
    assert r.status_code==200,r.text
    before=r.json();cmd(db,'account',name='Checking',account_type='bank')
    path='/api/v1/accounting/report-runs/'+before['id']
    assert client.get(path,headers=tenant_headers).json()==before
    assert client.get(path+'/package',headers=tenant_headers).status_code==409
    assert client.get(path+'/package?draft=true',headers=tenant_headers).status_code==200

def test_evidence_versions_and_hashes(client,tenant_headers):
    def upload(body,**fields): return client.post('/api/v1/accounting/evidence',headers=tenant_headers,data={'source_key':'invoice-1',**fields},files={'file':('invoice.txt',body,'text/plain')})
    first=upload(b'first').json()
    assert upload(b'first').json()['id']==first['id']
    assert upload(b'amended').status_code==409
    assert upload(b'amended',supersedes_id=first['id']).json()['id']!=first['id']
    assert client.get('/api/v1/accounting/evidence/'+first['id']+'/original',headers=tenant_headers).content==b'first'

def test_statement_mismatch_is_not_saved(db):
    policy_setup(db)
    with pytest.raises(Exception):bank(db,opening='100.00',closing='101.00')
    db.rollback()
    assert db.query(FinanceEvent).filter_by(kind='statement').count()==0

def test_partial_payments_and_split_transaction(db,truck):
    d=policy_setup(db);a,s=bank(db,rows='2026-09-21,-750.00,Multiple repairs,b1\n',closing='9250.00')
    one=bill(db,d,truck);two=bill(db,d,truck)
    tx=s.payload['_transactions'][0]['id']
    cmd(db,'payment',claim_id=one.id,amount='500.00',payer='business',transaction_id=tx)
    assert tx not in f.state(db,1,ASOF)['matches']
    cmd(db,'payment',claim_id=two.id,amount='250.00',payer='business',transaction_id=tx)
    assert tx in f.state(db,1,ASOF)['matches']
    assert f.cash_position(db,1,ASOF)['uncovered_bills']=='250.00'
    assert f.ledger_report(db,1,date.min,ASOF)['income_statement']['net_income']=='-1000.00'

def test_bulk_mutation_rejected(db):
    e=cmd(db,'account',name='Checking',account_type='bank')
    with pytest.raises(Exception): db.query(FinanceEvent).filter_by(id=e.id).update({'kind':'policy'})
    db.rollback()
    assert db.query(FinanceEvent).filter_by(id=e.id).one().kind=='account'

def test_reversal_preserves_history(db,truck):
    d=policy_setup(db);b=bill(db,d,truck)
    p=db.query(FinancePosting).filter_by(event_id=b.id).one()
    cmd(db,'reversal',when='2026-09-22',posting_id=p.id,reason='Invoice cancelled')
    assert f.ledger_report(db,1,date.min,ASOF)['income_statement']['net_income']=='-500.00'
    assert f.ledger_report(db,1,date.min,date(2026,9,22))['income_statement']['net_income']=='0.00'
    assert f.state(db,1,date(2026,9,22))['claims']=={}
    assert db.query(FinancePosting).count()==2

def test_pdf_rows_preserve_gallons_and_unknown_products():
    from app.services.settlement_evidence import normalize_77
    from tests.test_77_cargo_parser import PAGE_1, PAGE_2, PAGE_3
    p=normalize_77('\n'.join([PAGE_1, PAGE_2, PAGE_3]))
    assert p['fuel'][0]['gallons']=='170.42'
    assert p['fuel'][0]['product']=='unknown'
    assert p['loads'][0]['loaded_miles']=='735'

def test_refund_and_credit_do_not_add_expenses(db,truck):
    d=policy_setup(db)
    _,s=bank(db,rows='2026-09-21,-500.00,Repair,pay1\n2026-09-21,200.00,Refund,refund1\n',closing='9700.00')
    b=bill(db,d,truck)
    cmd(db,'payment',claim_id=b.id,amount='500.00',payer='business',transaction_id=s.payload['_transactions'][0]['id'])
    cmd(db,'credit_note',claim_id=b.id,amount='200.00',transaction_id=s.payload['_transactions'][1]['id'],evidence_id=d,description='Returned part')
    assert f.ledger_report(db,1,date.min,ASOF)['income_statement']['net_income']=='-300.00'
    assert f.cash_position(db,1,ASOF)['available']=='9700.00'
    b2=bill(db,d,truck)
    cmd(db,'credit_note',claim_id=b2.id,amount='100.00',evidence_id=d,description='Invoice discount')
    assert f.state(db,1,ASOF)['claims'][b2.id]['remaining']==f.D('400.00')

def test_closed_period_and_reopening(db,truck):
    d=policy_setup(db); bank(db)
    cmd(db,'policy',when='2026-01-01',timezone='America/New_York',approved=True,account_coverage_confirmed=True,opening_confirmed=True,history_confirmed=True,carrier_presentation_confirmed=True,owner_treatment_confirmed=True,depreciation_confirmed=True,tax_basis_confirmed=True,evidence_ids=[d])
    cmd(db,'journal',when='2026-01-01',description='Confirmed opening',evidence_id=d,cash_flow_classification='opening',lines=[{'account':'cash','debit':'10000.00'},{'account':'owner_equity','credit':'10000.00'}])
    assert f.readiness(db,1,ASOF)['status']=='pass'
    cmd(db,'close_period',start='2026-09-01',end='2026-09-21',reason='Reconciled close')
    with pytest.raises(Exception):bill(db,d,truck)
    db.rollback()
    cmd(db,'reopen_period',when='2026-09-22',start='2026-09-01',end='2026-09-21',reason='New supported invoice')
    bill(db,d,truck)

def test_assignment_keeps_history(db,truck):
    trailer1=Truck(name='Trailer 1',tenant_id=1,vehicle_type='trailer');trailer2=Truck(name='Trailer 2',tenant_id=1,vehicle_type='trailer');db.add_all([trailer1,trailer2]);db.commit()
    cmd(db,'assignment',when='2026-09-01',truck_id=truck.id,trailer_id=trailer1.id)
    cmd(db,'assignment',when='2026-09-15',truck_id=truck.id,trailer_id=trailer2.id)
    assert f.state(db,1,date(2026,9,14))['assignments'][0]['end'] is None
    current=f.state(db,1,ASOF)['assignments']
    assert current[0]['end']=='2026-09-14'
    assert current[1]['start']=='2026-09-15'

def test_auto_match_requires_unique_reference_and_approved_mapping(db,truck):
    d=policy_setup(db)
    b=cmd(db,'bill',evidence_id=d,source_ref='INV-9001',description='Repair',amount='500.00',category='repairs',asset_id=truck.id)
    a=cmd(db,'account',when='2026-01-01',name='Bank',account_type='bank')
    m=cmd(db,'csv_mapping',when='2026-01-01',name='Approved',date_column='Date',amount_column='Amount',description_column='Description',id_column='ID',approved_for_matching=True)
    source=doc(db,b'Date,Amount,Description,ID\n2026-09-21,-500.00,Payment INV-9001,txn1\n')
    cmd(db,'statement',account_id=a.id,mapping_id=m.id,evidence_id=source,start='2026-09-21',end='2026-09-21',opening='10000.00',closing='9500.00')
    assert len(f.auto_reconcile(db,1))==1
    db.commit()
    assert f.state(db,1,ASOF)['claims'][b.id]['remaining']==0
    assert f.auto_reconcile(db,1)==[]

def test_foreign_resources_are_hidden_even_under_valid_tenant(client,db,tenant_headers):
    from app.models.chart_of_accounts import ChartOfAccount
    db.add(Tenant(id=2,name='Other business'));db.commit()
    account=ChartOfAccount(tenant_id=2,code='1000',name='Other cash',account_type='Asset');db.add(account);db.commit()
    r=client.get(f'/api/accounting/chart-of-accounts/{account.id}',headers=tenant_headers)
    assert r.status_code==404
    assert r.json()['error']['code']=='RESOURCE_NOT_FOUND'
    assert r.headers['X-Request-ID']==r.json()['error']['trace_id']
    r=client.post('/api/v1/accounting/events',headers={**tenant_headers,'Idempotency-Key':'illegal-tenant'},json={'effective_date':'2026-09-21','payload':{'kind':'account','name':'Bank','account_type':'bank','tenant_id':2}})
    assert r.status_code==400


def test_cross_pair_repair_cannot_consume_other_reserve(db,truck):
    d=policy_setup(db);bank(db)
    other=Truck(name='609',tenant_id=1,vehicle_type='truck');db.add(other);db.commit()
    reserve=cmd(db,'reserve',pair_id=truck.id,purpose='repair',amount='1000.00',opening=True,note='Funded',evidence_id=d)
    with pytest.raises(Exception):cmd(db,'bill',evidence_id=d,source_ref='BAD-PAIR',description='Repair',amount='500.00',category='repairs',asset_id=other.id,pair_id=truck.id,reserve_id=reserve.id)
    db.rollback()
    assert f.state(db,1,ASOF)['reserves'][f'{truck.id}:repair:']['balance']==f.D('1000.00')

def test_cutover_requires_reconciled_current_snapshot(client,tenant_headers):
    r=client.post('/api/v1/accounting/report-runs',headers=tenant_headers,json={'start':'2026-09-01','end':'2026-09-21','as_of':'2026-09-21'}).json()
    attempted=client.post('/api/v1/accounting/events',headers={**tenant_headers,'Idempotency-Key':'cutover-test-key'},json={'effective_date':'2026-09-21','payload':{'kind':'activate_finance','report_id':r['id'],'browser_acceptance_confirmed':True}})
    assert attempted.status_code==409
    assert attempted.json()['error']['code']=='CUTOVER_BLOCKED'
    assert not client.get('/api/v1/accounting/context',headers=tenant_headers).json()['home_enabled']


def test_mixed_card_cashflow_requires_full_supported_allocation(db,truck):
    d=policy_setup(db)
    _,bs=bank(db,rows='2026-09-21,-500.00,Card repayment,b1\n',closing='9500.00')
    _,cs=bank(db,rows='2026-09-21,-500.00,Charges,c1\n2026-09-21,500.00,Repayment,c2\n',opening='0.00',closing='0.00',typ='card')
    operating=cmd(db,'bill',evidence_id=d,source_ref='repair-mixed',description='Repair',amount='300.00',category='repairs',asset_id=truck.id)
    equipment=cmd(db,'bill',evidence_id=d,source_ref='equipment-mixed',description='Equipment acquisition',amount='200.00',category='equipment',asset_id=truck.id)
    for claim,amount in [(operating,'300.00'),(equipment,'200.00')]:
        cmd(db,'payment',claim_id=claim.id,amount=amount,payer='card',transaction_id=cs.payload['_transactions'][0]['id'])
    match=dict(transaction_id=bs.payload['_transactions'][0]['id'],match_type='card_repayment',counterpart_transaction_id=cs.payload['_transactions'][1]['id'])
    with pytest.raises(Exception):cmd(db,'bank_match',**match)
    db.rollback()
    cmd(db,'bank_match',**match,operating_amount='300.00',investing_amount='200.00')
    result=f.ledger_report(db,1,ASOF,ASOF)
    assert result['cash_flow']['operating']=='-300.00'
    assert result['cash_flow']['investing']=='-200.00'
    assert result['cash_flow']['net_change']=='-500.00'
    assert result['income_statement']['net_income']=='-300.00'


def test_ready_package_contains_originals_and_cutover_requires_current_snapshot(client,db,tenant_headers):
    import io,json,zipfile
    d=policy_setup(db);bank(db)
    cmd(db,'policy',when='2026-01-01',timezone='America/New_York',approved=True,account_coverage_confirmed=True,opening_confirmed=True,history_confirmed=True,carrier_presentation_confirmed=True,owner_treatment_confirmed=True,depreciation_confirmed=True,tax_basis_confirmed=True,evidence_ids=[d])
    cmd(db,'journal',when='2026-01-01',description='Confirmed opening',evidence_id=d,cash_flow_classification='opening',lines=[{'account':'cash','debit':'10000.00'},{'account':'owner_equity','credit':'10000.00'}])
    r=client.post('/api/v1/accounting/report-runs',headers=tenant_headers,json={'start':'2026-09-01','end':'2026-09-21','as_of':'2026-09-21'}).json()
    assert r['readiness']['status']=='pass'
    download=client.get(f"/api/v1/accounting/report-runs/{r['id']}/package",headers=tenant_headers)
    assert download.status_code==200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        frozen=json.loads(archive.read('report.json'))
        assert frozen['source_events'] and frozen['evidence_manifest']
        assert archive.read(f'evidence/{d}-source.csv')==b'evidence'
    assert not client.get('/api/v1/accounting/context',headers=tenant_headers).json()['home_enabled']
    cmd(db,'activate_finance',report_id=r['id'],browser_acceptance_confirmed=True)
    assert client.get('/api/v1/accounting/context',headers=tenant_headers).json()['home_enabled']
