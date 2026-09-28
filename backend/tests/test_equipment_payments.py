from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.models.truck import Truck
from app.models.finance import FinancePosting
from app.models.settlement import Settlement
from app.models.tenant import Tenant
from app.services import finance as f
from app.services.equipment_payments import summary, workspace
from app.services.investment_progress import investment_progress
from tests.test_finance import bank, cmd, doc, policy_setup, ASOF
from tests.test_investment_progress import asset as plan_asset


@pytest.fixture
def trailer(db):
    a=Truck(tenant_id=1,name='Trailer 3142',vehicle_type='trailer',purchase_date=date(2026,1,1),
            total_cost=75000,loan_amount=75000,investment_plans=plan_asset().investment_plans)
    db.add(a);db.commit();return a


def setup_payment(db, trailer, amount='900.00'):
    account, statement=bank(db,f'2026-09-21,-{amount},Dedicated HELOC payment,HELOC-42\n',closing=f.money(10000-Decimal(amount)))
    evidence=doc(db,b'HELOC statement interest and principal')
    payload=dict(asset_id=trailer.id,transaction_id=statement.payload['_transactions'][0]['id'],facility='HELOC ending 1234',
                 principal='500.00',interest='400.00',evidence_id=evidence,allocation_note='Trailer share reconciled to lender statement',split_confirmed=True)
    return account,statement,payload


def test_payment_requires_bank_evidence_and_counts_principal_not_interest(db,trailer):
    account,statement,p=setup_payment(db,trailer)
    before=db.query(FinancePosting).count()
    e=cmd(db,'equipment_payment',key='same-bank-payment',**p)
    assert cmd(db,'equipment_payment',key='same-bank-payment',**p).id==e.id
    s=summary(db,1,trailer,ASOF)
    assert s['principal_paid']=='500.00'
    assert s['interest_paid']=='400.00'
    assert s['remaining_from_records']=='74500.00'
    assert s['payment_count']==1
    assert db.query(FinancePosting).count()==before  # Management record, not a duplicate loan/acquisition journal.
    assert workspace(db,1,ASOF)['transactions']==[]
    with pytest.raises(HTTPException,match=''):
        cmd(db,'equipment_payment',**p)
    db.rollback()
    with pytest.raises(HTTPException):
        cmd(db,'bank_match',transaction_id=p['transaction_id'],match_type='owner_distribution')


@pytest.mark.parametrize('change',[{'principal':'501.00'},{'transaction_id':'missing'},{'split_confirmed':False},{'evidence_id':'missing'}])
def test_reject_invalid_split_or_evidence(db,trailer,change):
    _,_,p=setup_payment(db,trailer)
    with pytest.raises((HTTPException,ValueError)):
        cmd(db,'equipment_payment',**{**p,**change})


def test_cross_tenant_and_posted_date_guard(db,trailer):
    _,_,p=setup_payment(db,trailer)
    with pytest.raises(HTTPException):cmd(db,'equipment_payment',when='2026-09-22',**p)
    db.rollback()
    db.add(Tenant(id=2,name='Other',business_type='logistics'));db.commit()
    other=Truck(tenant_id=2,name='Other trailer',vehicle_type='trailer',investment_plans=plan_asset().investment_plans)
    db.add(other);db.commit()
    with pytest.raises(HTTPException):cmd(db,'equipment_payment',**{**p,'asset_id':other.id})
    assert workspace(db,2,ASOF)['transactions']==[]


def test_correction_keeps_history_releases_transaction_and_restores_estimate(db,trailer):
    _,_,p=setup_payment(db,trailer)
    e=cmd(db,'equipment_payment',**p)
    cmd(db,'equipment_payment_void',when='2026-09-22',payment_id=e.id,reason='Wrong trailer; reassign')
    assert summary(db,1,trailer,ASOF)['principal_paid']=='0.00'
    assert summary(db,1,trailer,date(2026,9,22))['principal_paid']=='0.00'
    assert len(workspace(db,1,date(2026,9,22))['transactions'])==1
    with pytest.raises(HTTPException):cmd(db,'equipment_payment_void',when='2026-09-22',payment_id=e.id,reason='Again')
    db.rollback()
    cmd(db,'equipment_payment',**p)
    assert summary(db,1,trailer,date(2026,9,22))['principal_paid']=='500.00'
    assert summary(db,1,trailer,ASOF)['principal_paid']=='500.00'


def test_due_date_does_not_create_a_payment(db,trailer):
    d=doc(db)
    cmd(db,'equipment_payment_due',asset_id=trailer.id,due='2026-10-10',amount='900.00',facility='HELOC',evidence_id=d)
    s=summary(db,1,trailer,ASOF)
    assert s['due']['due']=='2026-10-10'
    assert s['payment_count']==0
    assert s['principal_paid']=='0.00'


def test_actual_payment_replaces_budget_and_extra_principal_reduces_available_cash_once(db,trailer):
    truck=Truck(tenant_id=1,name='Truck',vehicle_type='truck',default_repair_reserve_amount=300)
    db.add(truck);db.flush()
    db.add(Settlement(truck_id=truck.id,settlement_date=ASOF,gross_revenue=5000,expenses=1000,net_profit=3600,
                      trailer_income_split_trailer_id=trailer.id,trailer_income_split_amount=400))
    db.commit()
    _,_,p=setup_payment(db,trailer)
    def report():return f.report(db,1,ASOF,date(2026,9,27),date(2026,9,27))['earnings_plan']
    before=report();pair=before['pairs'][0]
    target=Decimal(pair['asset_deductions'][-1]['loan_target'])
    cmd(db,'equipment_payment',**p)
    after=report();pair=after['pairs'][0]
    assert pair['confirmed_payments']=='900.00'
    assert Decimal(after['planning_subtotal'])==Decimal(before['planning_subtotal'])+target-900
    assert sum(Decimal(r['amount']) for r in after['retention']['pairs'][0]['bridge'])==Decimal(after['planning_subtotal'])
    progress=investment_progress(db,1,trailer,date(2026,9,27))
    assert progress['recorded_payments']['principal_paid']=='500.00'
    assert progress['estimated_free_cash']=='-500.00'
    assert progress['actual_balance'] is None


def test_api_tenant_scope(client,db,trailer,monkeypatch):
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS','1')
    r=client.get('/api/v1/accounting/equipment-payments?as_of=2026-09-21',headers={'X-Tenant-ID':'1'})
    assert r.status_code==200
    assert r.json()['assets'][0]['id']==trailer.id


def test_unassigned_trailer_payment_still_reduces_business_estimate(db,trailer):
    _,_,p=setup_payment(db,trailer)
    before=f.report(db,1,ASOF,ASOF,ASOF)['earnings_plan']
    cmd(db,'equipment_payment',**p)
    after=f.report(db,1,ASOF,ASOF,ASOF)['earnings_plan']
    assert Decimal(after['unassigned_result'])==Decimal(before['unassigned_result'])-900
    assert next(c for c in f.readiness(db,1,ASOF)['checks'] if c['code']=='equipment_payment_books')['status']=='unknown'


def test_payment_below_budget_does_not_reduce_estimate_twice(db,trailer):
    truck=Truck(tenant_id=1,name='Truck',vehicle_type='truck',default_repair_reserve_amount=300)
    db.add(truck);db.flush()
    db.add(Settlement(truck_id=truck.id,settlement_date=ASOF,gross_revenue=5000,expenses=1000,net_profit=3600,trailer_income_split_trailer_id=trailer.id,trailer_income_split_amount=400));db.commit()
    _,_,p=setup_payment(db,trailer,amount='100.00')
    before=f.report(db,1,ASOF,date(2026,9,27),date(2026,9,27))['earnings_plan']
    cmd(db,'equipment_payment',**{**p,'principal':'60.00','interest':'40.00'})
    after=f.report(db,1,ASOF,date(2026,9,27),date(2026,9,27))['earnings_plan']
    assert after['planning_subtotal']==before['planning_subtotal']
    assert after['pairs'][0]['asset_deductions'][-1]['confirmed_payments']=='100.00'


def test_principal_cannot_exceed_trailer_borrowing(db,trailer):
    _,_,p=setup_payment(db,trailer,amount='75001.00')
    with pytest.raises(HTTPException):
        cmd(db,'equipment_payment',**{**p,'principal':'75001.00','interest':'0.00'})


def test_matched_statement_cannot_be_replaced(db,trailer):
    account,statement,p=setup_payment(db,trailer)
    cmd(db,'equipment_payment',**p)
    replacement=doc(db,b'Date,Amount,Description,ID\n2026-09-21,-899.00,Changed,HELOC-42\n')
    with pytest.raises(HTTPException):
        cmd(db,'statement',account_id=account.id,mapping_id=statement.payload['mapping_id'],evidence_id=replacement,
            start='2026-09-21',end='2026-09-21',opening='10000.00',closing='9101.00',supersedes_id=statement.id)


def test_closed_period_payment_cannot_be_voided(db,trailer):
    from app.models.finance import FinanceEvent
    _,_,p=setup_payment(db,trailer)
    event=cmd(db,'equipment_payment',**p)
    db.add(FinanceEvent(tenant_id=1,key='closed-test',digest='test',kind='close_period',effective_date=ASOF,payload={'start':'2026-09-01','end':'2026-09-21'}));db.commit()
    with pytest.raises(HTTPException):
        cmd(db,'equipment_payment_void',when='2026-09-22',payment_id=event.id,reason='Change source')
