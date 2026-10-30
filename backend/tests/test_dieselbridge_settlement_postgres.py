"""Prior-install upgrades and exact-once source receipt claims across PG sessions."""
import asyncio,base64,hashlib,json,os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,text,inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from app.migration_runner import _add_dieselbridge_settlement_observations
from app.models.dieselbridge import DieselBridgeRepairLink as Link,DieselBridgeRepairPayment as Payment
from app.models.finance import FinanceEvidence
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.schemas.dieselbridge_financial import VerifiedRepairPayment
from app.services import dieselbridge as d,dieselbridge_financial as financial
from tests.test_dieselbridge_postgres import postgres
from tests.test_dieselbridge_settlement import settled,payment
from tests.test_dieselbridge_financial import digest


def migration_check(engine):
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TABLE dbn_repair_links(id INTEGER PRIMARY KEY,accepted_payload JSON)')
        c.exec_driver_sql('CREATE TABLE dbn_repair_payments(id INTEGER PRIMARY KEY,tenant_id INTEGER,amount NUMERIC(18,2),reversal_event_id VARCHAR(36))')
        c.exec_driver_sql("INSERT INTO dbn_repair_links VALUES(1,'{}')")
        c.exec_driver_sql('INSERT INTO dbn_repair_payments VALUES(1,1,200.00,NULL)')
    _add_dieselbridge_settlement_observations(engine);_add_dieselbridge_settlement_observations(engine)
    with engine.begin() as c:
        assert c.exec_driver_sql('SELECT amount,source_attempt_id FROM dbn_repair_payments WHERE id=1').one()==(200,None)
        assert c.exec_driver_sql('SELECT source_settlement_payload,source_payment_review_reasons FROM dbn_repair_links').one()==(None,None)
        c.exec_driver_sql("INSERT INTO dbn_repair_payments(id,tenant_id,amount,source_shop_id,source_attempt_id) VALUES(2,1,200,'shop','attempt')")
    with pytest.raises(IntegrityError),engine.begin() as c:
        c.exec_driver_sql("INSERT INTO dbn_repair_payments(id,tenant_id,amount,source_shop_id,source_attempt_id) VALUES(3,1,200,'shop','attempt')")
    with engine.begin() as c:
        c.exec_driver_sql("UPDATE dbn_repair_payments SET reversal_event_id='reversal' WHERE id=2")
        c.exec_driver_sql("INSERT INTO dbn_repair_payments(id,tenant_id,amount,source_shop_id,source_attempt_id) VALUES(3,1,200,'shop','attempt')")
        c.exec_driver_sql("INSERT INTO dbn_repair_payments(id,tenant_id,amount,source_shop_id,source_attempt_id) VALUES(4,2,200,'shop','attempt')")
    assert any(i['name']=='uq_dbn_active_source_payment' and i['unique'] for i in inspect(engine).get_indexes('dbn_repair_payments'))


def test_sqlite_previous_install_upgrade_preserves_and_protects_claims():
    engine=create_engine('sqlite:///:memory:');migration_check(engine);engine.dispose()


@pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL not configured')
def test_postgres_previous_install_upgrade_preserves_and_protects_claims():
    url=make_url(os.environ['DB094_POSTGRES_TEST_URL'])
    if url.get_backend_name()!='postgresql' or not (url.database or '').startswith('db094_'):pytest.fail('Disposable db094_ database required')
    admin=create_engine(url);schema='db094_claim_upgrade_'+uuid4().hex
    with admin.begin() as c:c.exec_driver_sql('CREATE SCHEMA '+schema)
    engine=create_engine(url,connect_args={'options':'-c search_path='+schema})
    try:migration_check(engine)
    finally:
        engine.dispose()
        with admin.begin() as c:c.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')
        admin.dispose()


@pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL not configured')
def test_postgres_concurrent_source_claim_creates_one_payment_and_withdrawal(postgres,monkeypatch):
    engine,sessions,tenant=postgres
    monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','1')
    p=payment();row=settled(payments=[p]);row['vin']='1M8GDM9AXKP042788'
    row['revision']=digest({k:v for k,v in row.items() if k not in ('revision','settlement')})
    scope={'version':financial.VERSION,'shop_id':'fixture-shop','customer_id':'fixture-customer','items':[row]}
    value={**scope,'count':1,'complete':True,'snapshot_id':digest(scope)}
    async def request(self,path,params=None):return httpx.Response(200,json=value)
    monkeypatch.setattr(d.SourceClient,'request',request)
    with sessions() as db:
        asyncio.run(financial.sync_financial(db,tenant,'fixture',idempotency_key='create',automatic=True));db.commit()
        link=db.query(Link).filter_by(tenant_id=tenant).one();repair_id=link.repair_id;revision=link.accepted_revision
        proof_ids=[]
        for n in range(2):
            raw=f'Independent synthetic payment evidence {n}'.encode()
            proof=FinanceEvidence(tenant_id=tenant,sha256=hashlib.sha256(raw).hexdigest(),filename=f'receipt-{n}.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode(),source_key=f'claim-proof-{n}',extraction_version='elis-evidence-v1',extracted={})
            db.add(proof);db.flush();proof_ids.append(proof.id)
        db.commit()
    def apply(n):
        with sessions() as db:
            body=VerifiedRepairPayment(expected_revision=revision,amount='200.00',paid_date='2026-10-20',payer='owner',evidence_id=proof_ids[n],owner_payment_confirmed=True,note='Independent verified actual payment proof',source_attempt_id=p['attempt_id'],source_attempt_revision=p['revision'])
            try:
                financial.record_verified_payment(db,tenant,repair_id,body,f'concurrent-{n}');db.commit();return 'created'
            except HTTPException as exc:
                db.rollback();return exc.detail['code']
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(apply,range(2)))
    assert sorted(results)==['DUPLICATE_SOURCE_PAYMENT','created']
    with sessions() as db:
        assert db.query(Payment).filter_by(tenant_id=tenant).count()==1
        rows=db.query(RepairReserveLedger).filter_by(tenant_id=tenant).all()
        assert len(rows)==1 and str(rows[0].amount)=='200.00'
