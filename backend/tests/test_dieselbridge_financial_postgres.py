"""Opt-in financial import concurrency on an explicitly disposable PostgreSQL DB."""
import asyncio
from collections import Counter
import os
from decimal import Decimal
import httpx
import pytest
from app.models.truck import Truck
from app.models.repair import Repair
from app.models.dieselbridge import DieselBridgeRepairLink
from app.models.finance import FinanceEvent, FinanceLine, FinancePosting, FinanceEvidence
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.schemas.dieselbridge_financial import VerifiedRepairPayment, RepairPaymentReversal
from app.services import dieselbridge as d
from app.services import dieselbridge_financial as financial
from tests.test_dieselbridge_postgres import postgres
from tests.test_dieselbridge_financial import item, digest

pytestmark=pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL test database not configured')


def test_postgres_fifteen_financial_concurrent_import_partial_and_reversal(postgres,monkeypatch):
    engine,sessions,tenant=postgres
    monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','1')
    with sessions() as db:
        a=db.query(Truck).filter_by(tenant_id=tenant).one();a.vin='VIN603'
        b=Truck(tenant_id=tenant,name='609',vehicle_type='truck',vin='VIN609');db.add(b);db.commit()
        ids=a.id,b.id
    items=[item(n,vin='VIN603' if n<=6 else 'VIN609',vehicle_id='vehicle603' if n<=6 else 'vehicle609') for n in range(1,16)]
    body={'version':financial.VERSION,'shop_id':'fixture-shop','customer_id':'fixture-customer','items':items}
    value={**body,'count':15,'complete':True,'snapshot_id':digest(body)}
    async def request(self,path,params=None):
        assert path=='repair-orders/financial'
        await asyncio.sleep(.03)
        return httpx.Response(200,json=value)
    monkeypatch.setattr(d.SourceClient,'request',request)
    def apply(key):
        with sessions() as db:
            result=asyncio.run(financial.sync_financial(db,tenant,'fixture',idempotency_key=key,automatic=True))
            db.commit();return result
    async def concurrent():
        return await asyncio.wait_for(asyncio.gather(asyncio.to_thread(apply,'financial-a'),asyncio.to_thread(apply,'financial-b')),8)
    results=asyncio.run(concurrent())
    assert sorted(r['created'] for r in results)==[0,15]
    with sessions() as db:
        links=db.query(DieselBridgeRepairLink).filter_by(tenant_id=tenant).all()
        rows=db.query(Repair).join(Truck).filter(Truck.tenant_id==tenant).all()
        assert len(rows)==len(links)==15 and Counter(r.truck_id for r in rows)=={ids[0]:6,ids[1]:9}
        assert db.query(FinanceEvent).filter_by(tenant_id=tenant,kind='bill').count()==15
        assert db.query(RepairReserveLedger).filter_by(tenant_id=tenant).count()==0
        assert db.query(FinanceEvent).filter_by(tenant_id=tenant,kind='payment').count()==0
        link=links[0]
        import base64,hashlib
        raw=b'Fixture actual owner payment receipt 200 USD'
        proof=FinanceEvidence(tenant_id=tenant,sha256=hashlib.sha256(raw).hexdigest(),filename='actual-fixture-receipt.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode(),source_key='fixture-receipt',extraction_version='elis-evidence-v1',extracted={})
        db.add(proof);db.flush()
        payment=VerifiedRepairPayment(expected_revision=link.accepted_revision,amount='200.00',paid_date='2026-10-20',payer='owner',evidence_id=proof.id,owner_payment_confirmed=True,note='Verified fixture partial payment')
        result=financial.record_verified_payment(db,tenant,link.repair_id,payment,'fixture-partial')
        db.commit()
        assert result['recorded_paid_amount']=='200.00' and result['recorded_balance_due']=='800.00'
        assert db.query(RepairReserveLedger).filter_by(tenant_id=tenant,entry_type='withdrawal').one().amount==Decimal('200.00')
        p=result['payments'][0]
        reversal=RepairPaymentReversal(expected_revision=link.accepted_revision,reversal_date='2026-10-21',reason='Fixture allocation correction')
        result=financial.reverse_verified_payment(db,tenant,link.repair_id,p['id'],reversal,'fixture-reverse');db.commit()
        assert result['recorded_paid_amount']=='0.00' and result['recorded_balance_due']=='1000.00'
        assert db.query(RepairReserveLedger).filter_by(tenant_id=tenant,entry_type='withdrawal_reversal').one().amount==Decimal('200.00')
        assert db.query(FinanceEvent).filter_by(tenant_id=tenant,kind='bill').count()==15
    assert apply('financial-replay')['unchanged']==15
