"""Full-source catch-up closes missed-event gaps; payments remain separately verified."""
import asyncio
from datetime import date,timedelta
import json
from decimal import Decimal
import httpx
import pytest
from sqlalchemy.orm import sessionmaker
from app.models.dieselbridge import DieselBridgeRepairLink as Link,DieselBridgeRepairPayment as Payment,DieselBridgeFinancialOperation as Operation
from app.models.finance import FinanceEvent
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger as Ledger
from app.models.tenant import Tenant
from app.models.truck import Truck
from app.services import dieselbridge as d,dieselbridge_financial as financial,dieselbridge_financial_events as events
from app.schemas.dieselbridge_financial import HistoricalBusinessCashPayment
from tests.test_dieselbridge_financial import setup,source,snapshot,sync,item,digest,C
from tests.test_dieselbridge_settlement import settled,payment

NOW=events.datetime(2026,10,30,12,tzinfo=events.timezone.utc)

@pytest.fixture(autouse=True)
def worker_enabled(monkeypatch):monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_WORKER_ENABLED','true')

def run(db,**kwargs):return asyncio.run(events.reconcile_connections_once(sessionmaker(bind=db.get_bind(),autoflush=False),**kwargs))


def test_initial_full_refetch_imports_missed_finalized_invoices_once_and_never_pays(monkeypatch,db):
    trailer=Truck(tenant_id=1,name='Trailer',vehicle_type='trailer',vin='TRAILER1');db.add(trailer);db.commit()
    source(monkeypatch,snapshot([item(),item(2,vin='TRAILER1')]))
    result=run(db,now=NOW);db.expire_all()
    assert result['connections'][0]['result']['created']==2
    assert {r.truck_id for r in db.query(Repair)}=={1,trailer.id}
    assert db.query(FinanceEvent).filter_by(kind='bill').count()==2
    assert db.query(Payment).count()==db.query(Ledger).count()==0
    assert run(db,now=NOW)['connections'][0]['result']['created']==2  # durable operation replay
    assert run(db,now=NOW+timedelta(hours=1))['connections'][0]['result']['unchanged']==2
    assert db.query(Repair).count()==2


def test_changed_and_missing_invoice_is_held_without_rewriting_cost(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));run(db,now=NOW)
    source(monkeypatch,snapshot([item(total='1200.00')]))
    assert run(db,now=NOW+timedelta(hours=1))['connections'][0]['result']['review_required']==1
    db.expire_all();assert db.query(Repair).one().cost==Decimal('1000')
    assert db.query(Link).one().state=='review_required'
    source(monkeypatch,snapshot([]));run(db,now=NOW+timedelta(hours=2));db.expire_all()
    assert db.query(Link).one().state=='access_removed'
    assert db.query(FinanceEvent).filter_by(kind='bill').count()==1
    assert db.query(Payment).count()==db.query(Ledger).count()==0


@pytest.mark.parametrize('flag',['ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','ELIS_DIESELBRIDGE_FINANCIAL_WORKER_ENABLED'])
def test_catchup_requires_both_explicit_enablements(monkeypatch,db,flag):
    monkeypatch.delenv(flag)
    async def forbidden(*args,**kwargs):raise AssertionError('Source must not be fetched')
    assert run(db,sync_fn=forbidden,now=NOW)=={'status':'disabled','connections':[]}
    assert db.query(Repair).count()==0


def test_connections_commit_independently_and_never_expose_failure_details(monkeypatch,db):
    db.add(Tenant(id=2,name='Second tenant',business_type='logistics'));db.commit()
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS',json.dumps([C,{**C,'tenant_id':2,'slug':'second'}]))
    async def fake(session,tenant,slug,**kwargs):
        session.add(Truck(tenant_id=tenant,name='Catchup fixture',vehicle_type='truck'))
        session.flush()
        if tenant==1:raise RuntimeError('private source credential must never be recorded')
        return {'created':0,'unchanged':0,'review_required':0,'blocked':0}
    result=run(db,sync_fn=fake,now=NOW);db.expire_all()
    assert result['connections'][0]['status']=='retry'
    assert result['connections'][0]['error_code']=='FINANCIAL_SYNC_FAILED'
    assert 'private source' not in str(result)
    assert result['connections'][1]['status']=='completed'
    assert db.query(Truck).filter_by(name='Catchup fixture',tenant_id=1).count()==0
    assert db.query(Truck).filter_by(name='Catchup fixture',tenant_id=2).count()==1


def test_fifteen_recorded_payments_survive_catchup_and_new_final_invoice(monkeypatch,db):
    monkeypatch.setenv('ELIS_DIESELBRIDGE_HISTORICAL_CASH_ENABLED','1')
    rows=[];attempts={}
    for n in range(1,16):
        p=payment(n,amount='1000.00');row=settled(payments=[p])
        row.update(repair_order_id=f'ro-{n}',order_number=f'RO{n}')
        row['invoice'].update(invoice_id=f'invoice-{n}',invoice_number=f'INV{n}')
        row['invoice']['revision']=digest({k:v for k,v in row['invoice'].items() if k!='revision'})
        row['revision']=digest({k:v for k,v in row.items() if k not in ('revision','settlement')})
        rows.append(row);attempts[row['repair_order_id']]=p
    source(monkeypatch,snapshot(rows));sync(db);db.commit()
    for link in db.query(Link).all():
        p=attempts[link.repair_order_id]
        body=HistoricalBusinessCashPayment(expected_revision=link.accepted_revision,amount='1000.00',paid_date='2026-10-20',source_attempt_id=p['attempt_id'],source_attempt_revision=p['revision'],business_cash_handover_confirmed=True,actual_handover_date_confirmed=True,unreconciled_cash_coverage_acknowledged=True,note='Owner verified actual business cash handover for fixture.')
        financial.record_historical_cash_payment(db,1,link.repair_id,body,'historical-'+link.repair_order_id,'fixture-owner')
    db.commit();before={p.id:(p.event_id,p.amount,p.reserve_withdrawal_id) for p in db.query(Payment)}
    monkeypatch.delenv('ELIS_DIESELBRIDGE_HISTORICAL_CASH_ENABLED')
    assert run(db,now=NOW)['connections'][0]['result']['unchanged']==15
    source(monkeypatch,snapshot(rows+[item(16)]))
    assert run(db,now=NOW+timedelta(hours=1))['connections'][0]['result']['created']==1
    db.expire_all()
    assert db.query(Repair).count()==db.query(FinanceEvent).filter_by(kind='bill').count()==16
    assert db.query(Payment).count()==db.query(Ledger).count()==15
    assert {p.id:(p.event_id,p.amount,p.reserve_withdrawal_id) for p in db.query(Payment)}==before
    assert sum((r.amount for r in db.query(Ledger)),Decimal('0'))==Decimal('15000')


def test_worker_runs_initial_and_periodic_catchup_even_with_continuous_events(monkeypatch):
    calls=[];stop=asyncio.Event();clock=[NOW]
    async def catchup(*args,**kwargs):calls.append(kwargs['now']);return {'status':'completed','connections':[]}
    async def pending(*args,**kwargs):
        clock[0]+=timedelta(hours=1)
        if len(calls)>=2:stop.set()
        return {'processed':1,'status':'completed'}
    monkeypatch.setattr(events,'reconcile_connections_once',catchup)
    monkeypatch.setattr(events,'process_pending_once',pending)
    monkeypatch.setattr(events,'utcnow',lambda:clock[0])
    asyncio.run(events.financial_events_worker(None,stop))
    assert calls==[NOW,NOW+timedelta(hours=1)]


@pytest.mark.parametrize('value',['{}','[{"tenant_id":true,"slug":"shop"}]','[{"tenant_id":1}]'])
def test_invalid_server_scope_configuration_never_fetches(monkeypatch,db,value):
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS',value)
    async def forbidden(*args,**kwargs):raise AssertionError('Invalid scope must not fetch')
    assert run(db,sync_fn=forbidden,now=NOW)['status']=='configuration_error'
    assert db.query(Repair).count()==0


def test_unauthorized_feed_and_inactive_tenant_cannot_import(monkeypatch,db):
    body=snapshot([item()]);body['customer_id']='another-customer';source(monkeypatch,body)
    assert run(db,now=NOW)['connections'][0]['error_code']=='SOURCE_PROTOCOL_ERROR'
    assert db.query(Repair).count()==0
    tenant=db.get(Tenant,1);tenant.is_active=False;db.commit()
    async def forbidden(*args,**kwargs):raise AssertionError('Inactive tenant must not fetch')
    assert run(db,sync_fn=forbidden,now=NOW)['connections'][0]['error_code']=='CONNECTION_SCOPE_CHANGED'
