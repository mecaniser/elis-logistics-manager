"""Concurrent historical receipts share the normal business lock and atomic ledger."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import os
import httpx
import pytest
from app.models.dieselbridge import DieselBridgeRepairLink as Link, DieselBridgeRepairPayment as Payment
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.models.finance import FinanceEvent
from app.models.truck import Truck
from app.schemas.dieselbridge_financial import HistoricalBusinessCashPayment
from app.services import dieselbridge as d, dieselbridge_financial as f
from tests.test_dieselbridge_postgres import postgres
from tests.test_dieselbridge_settlement import settled, payment
from tests.test_dieselbridge_financial import digest

pytestmark=pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL test database not configured')


def test_postgres_concurrent_historical_payment_replays_exactly_once(postgres,monkeypatch):
    _,sessions,tenant=postgres
    monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','1')
    monkeypatch.setenv('ELIS_DIESELBRIDGE_HISTORICAL_CASH_ENABLED','1')
    p=payment(amount='1000.00');row=settled(payments=[p])
    with sessions() as db:row['vin']=db.query(Truck).filter_by(tenant_id=tenant).one().vin
    row['revision']=digest({k:v for k,v in row.items() if k not in ('revision','settlement')})
    raw={'version':f.VERSION,'shop_id':'fixture-shop','customer_id':'fixture-customer','items':[row]}
    manifest={**raw,'count':1,'complete':True,'snapshot_id':digest(raw)}
    async def request(self,path,params=None):return httpx.Response(200,json=manifest)
    monkeypatch.setattr(d.SourceClient,'request',request)
    with sessions() as db:
        asyncio.run(f.sync_financial(db,tenant,'fixture',idempotency_key='initial',automatic=True));db.commit()
        link=db.query(Link).filter_by(tenant_id=tenant).one();repair_id=link.repair_id
        body=HistoricalBusinessCashPayment(expected_revision=link.accepted_revision,amount='1000.00',paid_date='2026-10-20',
            source_attempt_id=p['attempt_id'],source_attempt_revision=p['revision'],business_cash_handover_confirmed=True,
            actual_handover_date_confirmed=True,unreconciled_cash_coverage_acknowledged=True,note='Owner confirmed historical business cash and actual handover date.')
    def apply(_):
        with sessions() as db:
            result=f.record_historical_cash_payment(db,tenant,repair_id,body,'same-key','authenticated-owner');db.commit();return result
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(apply,range(2)))
    assert results[0]==results[1] and results[0]['recorded_balance_due']=='0.00'
    with sessions() as db:
        assert db.query(Payment).filter_by(tenant_id=tenant).count()==1
        assert db.query(RepairReserveLedger).filter_by(tenant_id=tenant,source_type='dbn_payment').one().amount==Decimal('1000.00')
        assert db.query(FinanceEvent).filter_by(tenant_id=tenant,kind='payment').count()==1
