"""Independent worker replicas and webhook work share the tenant transaction lock."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json,os
import httpx
import pytest
from app.models.truck import Truck
from app.models.repair import Repair
from app.models.dieselbridge import DieselBridgeRepairLink,DieselBridgeRepairPayment,DieselBridgeFinancialOperation
from app.models.finance import FinanceEvent
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.services import dieselbridge as d,dieselbridge_financial as financial,dieselbridge_financial_events as events
from tests.test_dieselbridge_postgres import postgres
from tests.test_dieselbridge_financial import item,digest

pytestmark=pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL test database not configured')
NOW=datetime(2026,11,1,12,tzinfo=timezone.utc)

@pytest.mark.parametrize('other_worker',['catchup','event_sync'])
def test_postgres_replicas_and_event_races_create_one_cost_without_payments(postgres,monkeypatch,other_worker):
    _,sessions,tenant=postgres
    for flag in ['ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','ELIS_DIESELBRIDGE_FINANCIAL_WORKER_ENABLED']:monkeypatch.setenv(flag,'true')
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS',json.dumps([{'tenant_id':tenant,'slug':'fixture'}]))
    with sessions() as db:vin=db.query(Truck).filter_by(tenant_id=tenant).one().vin
    row=item(vin=vin)
    raw={'version':financial.VERSION,'shop_id':'fixture-shop','customer_id':'fixture-customer','items':[row]}
    body={**raw,'complete':True,'count':1,'snapshot_id':digest(raw)}
    async def request(self,path,params=None):
        await asyncio.sleep(.02)
        return httpx.Response(200,json=body)
    monkeypatch.setattr(d.SourceClient,'request',request)
    def run(i):
        if i==1 and other_worker=='event_sync':
            with sessions() as db:
                result=asyncio.run(financial.sync_financial(db,tenant,'fixture',repair_order_ids=[row['repair_order_id']],idempotency_key='wakeup:fixture',automatic=True));db.commit();return result
        return asyncio.run(events.reconcile_connections_once(sessions,now=NOW))
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert all(r.get('status')=='completed' if 'status' in r else r['blocked']==0 for r in results)
    with sessions() as db:
        assert db.query(DieselBridgeRepairLink).filter_by(tenant_id=tenant).count()==1
        assert db.query(FinanceEvent).filter_by(tenant_id=tenant,kind='bill').count()==1
        assert db.query(DieselBridgeRepairPayment).filter_by(tenant_id=tenant).count()==0
        assert db.query(RepairReserveLedger).filter_by(tenant_id=tenant).count()==0
        assert db.query(DieselBridgeFinancialOperation).filter_by(tenant_id=tenant,kind='sync').count()==(1 if other_worker=='catchup' else 2)
