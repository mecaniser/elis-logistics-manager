"""Occurrence review uses native PostgreSQL dates and immutable evidence."""
import asyncio
import os
from datetime import date
import httpx
import pytest
from app.models.dieselbridge import DieselBridgeRepairLink as Link
from app.models.repair import Repair
from app.models.truck import Truck
from app.models.finance import FinanceEvent, FinanceEvidence
from app.schemas.dieselbridge_financial import ReconciliationNoteInput, SourceReviewApply
from app.services import dieselbridge as d, dieselbridge_financial as financial, dieselbridge_reconciliation as notes
from tests.test_dieselbridge_postgres import postgres
from tests.test_dieselbridge_financial import item, snapshot

pytestmark=pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL test database not configured')


def test_postgres_date_review_corrects_unpaid_bill_and_retains_source(postgres,monkeypatch):
    _,sessions,tenant=postgres
    monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','1')
    with sessions() as db:
        asset=db.query(Truck).filter_by(tenant_id=tenant).one()
        row=item(vin=asset.vin)
        manifest=snapshot([row]);manifest['shop_id']='fixture-shop';manifest['customer_id']='fixture-customer'
        manifest['snapshot_id']=financial.digest({k:manifest[k] for k in ('version','shop_id','customer_id','items')})
        async def request(self,path,params=None):return httpx.Response(200,json=manifest)
        monkeypatch.setattr(d.SourceClient,'request',request)
        asyncio.run(financial.sync_financial(db,tenant,'fixture',idempotency_key='initial',automatic=True));db.commit()
        link=db.query(Link).filter_by(tenant_id=tenant).one()
        decision=notes.append(db,tenant,'fixture','ro-1',ReconciliationNoteInput(note='Owner confirms completion July13.',confirmed_service_date='2026-07-13',date_treatment='confirmed_service_date',expected_source_revision=row['revision']),'date-review','fixture-owner');db.commit()
        preview,*_=asyncio.run(financial.review_preview(db,tenant,link.repair_id,link.accepted_revision))
        body=SourceReviewApply(expected_revision=link.accepted_revision,expected_review_digest=preview['review_digest'],note='Apply owner-confirmed historical completion date.')
        result=asyncio.run(financial.apply_source_review(db,tenant,link.repair_id,body,'apply-date'));db.commit()
        assert asyncio.run(financial.apply_source_review(db,tenant,link.repair_id,body,'apply-date'))==result
        assert db.get(Repair,link.repair_id).repair_date==date(2026,7,13)
        assert db.query(FinanceEvent).filter_by(tenant_id=tenant,id=link.bill_event_id).one().effective_date==date(2026,7,13)
        evidence=db.get(FinanceEvidence,link.evidence_id)
        assert evidence.extracted['date_decision']['id']==decision['id']
        assert evidence.extracted['source']['work_completed_at']==row['work_completed_at']
        assert db.query(FinanceEvent).filter_by(tenant_id=tenant,kind='payment').count()==0
