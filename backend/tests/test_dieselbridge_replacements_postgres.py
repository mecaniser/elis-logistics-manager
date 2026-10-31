import asyncio,json,os,threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
import httpx,pytest
from fastapi import HTTPException
from app.models.repair import Repair
from app.models.truck import Truck
from app.models.dieselbridge import DieselBridgeFinancialOperation as Operation
from app.services import dieselbridge as d,dieselbridge_financial as financial,dieselbridge_replacements as replacement,finance as f
from app.routers.repairs import update_repair
from app.schemas.dieselbridge_financial import TemporaryReplacementPreview as Preview,TemporaryReplacementApply as Apply
from tests.test_dieselbridge_postgres import postgres
from tests.test_dieselbridge_financial import item,snapshot

pytestmark=pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL test database not configured')


def test_legacy_edit_serializes_before_replacement_and_invalidates_plan(postgres,monkeypatch):
    engine,sessions,tenant=postgres
    monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','1')
    with sessions() as db:
        truck=db.query(Truck).filter_by(tenant_id=tenant).one()
        row=item(vin=truck.vin)
        body=snapshot([row]);body['shop_id']='fixture-shop';body['customer_id']='fixture-customer'
        raw={k:body[k] for k in ('version','shop_id','customer_id','items')};body['snapshot_id']=financial.digest(raw)
        async def request(self,path,params=None):return httpx.Response(200,json=body)
        monkeypatch.setattr(d.SourceClient,'request',request)
        asyncio.run(financial.sync_financial(db,tenant,'fixture',idempotency_key='initial',automatic=True))
        old=Repair(truck_id=truck.id,repair_date=date(2026,3,30),cost=Decimal('150.00'),title='Temporary')
        db.add(old);db.commit();old_id=old.id
        p=asyncio.run(replacement.preview(db,tenant,'fixture',Preview(repair_order_id='ro-1',legacy_repair_ids=[old_id],correction_date='2026-10-22')))
    apply_body=Apply(repair_order_id='ro-1',legacy_repair_ids=[old_id],correction_date='2026-10-22',expected_plan_digest=p['plan_digest'],confirmed_same_job=True,reviewed_existing_effects=True,reason='Reviewed replacement')
    locked=threading.Event();release=threading.Event();started=threading.Event()
    def edit():
        with sessions() as db:
            f.lock_business(db,tenant);locked.set();assert release.wait(3)
            asyncio.run(update_repair(old_id,repair_update_json=json.dumps({'cost':151}),images=[],db=db,tenant_id=tenant))
    def apply():
        with sessions() as db:
            started.set()
            try:asyncio.run(replacement.apply(db,tenant,'fixture',apply_body,'replacement'))
            except HTTPException as error:db.rollback();return error.detail
            db.commit();return 'unexpected success'
    with ThreadPoolExecutor(max_workers=2) as pool:
        edited=pool.submit(edit);assert locked.wait(2)
        replaced=pool.submit(apply);assert started.wait(2)
        assert not replaced.done();release.set();edited.result(timeout=5)
        assert 'STALE_PLAN' in str(replaced.result(timeout=5))
    with sessions() as db:
        assert db.get(Repair,old_id).archived_at is None and db.get(Repair,old_id).cost==Decimal('151.00')
        assert db.query(Operation).filter_by(tenant_id=tenant,kind='temp_replace').count()==0
