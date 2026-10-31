"""Reviewed dates control occurrence only, with immutable source-bound evidence."""
from datetime import date
import asyncio
import pytest
from fastapi import HTTPException
from app.models.repair import Repair
from app.models.dieselbridge import DieselBridgeRepairLink as Link
from app.schemas.dieselbridge_financial import ReconciliationNoteInput, SourceReviewApply
from app.services import dieselbridge_financial as financial, dieselbridge_reconciliation as notes
from tests.test_dieselbridge_financial import setup, source, snapshot, item, sync, owner_payment
from tests.test_dieselbridge_reconciliation_notes import history


def decide(db,row,day='2026-07-13',**changes):
    body=dict(note='Owner confirmed service completion; retain original DBN and ETS dates.',source_references=['DBN invoice 000021', 'ETSINV-1183'],confirmed_service_date=day,date_treatment='confirmed_service_date',expected_source_revision=row['revision'])
    body.update(changes)
    return notes.append(db,1,'shop',row['repair_order_id'],ReconciliationNoteInput(**body),'date-'+str(changes.get('supersedes_note_id','first')),'owner')


@pytest.mark.parametrize('day',['2026-07-13','2026-08-05'])
def test_confirmed_date_controls_preview_import_bill_and_replay(monkeypatch,db,day):
    history(db);row=item();source(monkeypatch,snapshot([row]))
    decision=decide(db,row,day);db.commit()
    notes.append(db,1,'shop','ro-1',ReconciliationNoteInput(note='Additional narrative does not erase reviewed date.'),'narrative','owner')
    preview=asyncio.run(financial.preview_financial(db,1,'shop'))
    assert preview['rows'][0]['repair_date']==day
    assert preview['rows'][0]['date_decision']['id']==decision['id']
    sync(db);db.commit();sync(db,'replay');db.commit()
    repair=db.query(Repair).one();link=db.query(Link).one()
    assert repair.repair_date==date.fromisoformat(day)
    from app.models.finance import FinanceEvent, FinanceEvidence
    assert db.query(FinanceEvent).filter_by(id=link.bill_event_id).one().effective_date==repair.repair_date
    assert db.get(FinanceEvidence,link.evidence_id).extracted['date_decision']['id']==decision['id']
    assert len(notes.for_link(db,1,link)['reconciliation_notes'])==2


def test_date_decision_requires_authorized_fresh_source_and_explicit_correction(monkeypatch,db):
    history(db);row=item();source(monkeypatch,snapshot([row]))
    with pytest.raises(HTTPException):decide(db,row,expected_source_revision='0'*64)
    first=decide(db,row);db.commit()
    with pytest.raises(HTTPException):decide(db,row,'2026-08-05')
    decide(db,row,'2026-08-05',supersedes_note_id=first['id']);db.commit()
    source(monkeypatch,snapshot([item(description='Changed source work')]))
    assert 'date_decision_source_changed' in asyncio.run(financial.preview_financial(db,1,'shop'))['rows'][0]['blockers']


def test_reviewed_date_change_requires_explicit_unpaid_review(monkeypatch,db):
    history(db);row=item();source(monkeypatch,snapshot([row]));sync(db);db.commit()
    link=db.query(Link).one();decide(db,row);db.commit()
    preview=asyncio.run(financial.preview_financial(db,1,'shop'))
    assert preview['rows'][0]['action']=='review_required'
    assert db.query(Repair).one().repair_date==date(2026,10,1)
    review,*_=asyncio.run(financial.review_preview(db,1,link.repair_id,link.accepted_revision))
    assert review['action']=='replace_unpaid_invoice' and review['can_apply']
    body=SourceReviewApply(expected_revision=link.accepted_revision,expected_review_digest=review['review_digest'],note='Apply confirmed historical completion date')
    asyncio.run(financial.apply_source_review(db,1,link.repair_id,body,'review-date'));db.commit()
    assert db.query(Repair).one().repair_date==date(2026,7,13)


def test_paid_repair_date_cannot_silently_move(monkeypatch,db):
    history(db);row=item();source(monkeypatch,snapshot([row]));sync(db);link=db.query(Link).one();owner_payment(db,link);db.commit()
    decide(db,row);db.commit()
    review,*_=asyncio.run(financial.review_preview(db,1,link.repair_id,link.accepted_revision))
    assert not review['can_apply'] and 'PAYMENT_CORRECTION_REQUIRED' in review['blockers']
    assert db.query(Repair).one().repair_date==date(2026,10,1)


def test_explicit_return_to_source_default_and_stale_preview(monkeypatch,db):
    history(db);row=item();source(monkeypatch,snapshot([row]));first=decide(db,row);db.commit()
    old=asyncio.run(financial.preview_financial(db,1,'shop'))
    decide(db,row,day=None,date_treatment='source_default',supersedes_note_id=first['id']);db.commit()
    current=asyncio.run(financial.preview_financial(db,1,'shop'))
    assert current['rows'][0]['repair_date']=='2026-10-01'
    assert current['plan_digest']!=old['plan_digest']
    with pytest.raises(HTTPException):
        asyncio.run(financial.sync_financial(db,1,'shop',idempotency_key='stale',expected_plan_digest=old['plan_digest']))
    assert db.query(Repair).count()==0


def test_source_completion_then_invoice_fallback(monkeypatch,db):
    row=item(work_completed_at=None,service_date=None);source(monkeypatch,snapshot([row]));sync(db)
    assert db.query(Repair).one().repair_date==date(2026,10,19)


def test_closed_period_blocks_date_correction(monkeypatch,db):
    from app.models.finance import FinanceEvent
    history(db);row=item();source(monkeypatch,snapshot([row]));sync(db);link=db.query(Link).one();db.commit()
    decide(db,row);db.add(FinanceEvent(tenant_id=1,key='closed-july',kind='close_period',effective_date=date(2026,8,1),payload={'start':'2026-07-01','end':'2026-07-31'},digest='c'*64));db.commit()
    review,*_=asyncio.run(financial.review_preview(db,1,link.repair_id,link.accepted_revision))
    assert not review['can_apply'] and 'PERIOD_CLOSED' in review['blockers']


def test_no_access_no_date_decision_and_disabled_mode_can_prepare(monkeypatch,db):
    history(db);row=item(authorization='attribution_required');source(monkeypatch,snapshot([row]))
    with pytest.raises(HTTPException) as exc:decide(db,row)
    assert exc.value.detail['code']=='SOURCE_ACCESS_REQUIRED'
    row=item();source(monkeypatch,snapshot([row]));monkeypatch.delenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED')
    decide(db,row);db.commit()
    assert db.query(Repair).count()==0


def test_narrative_cannot_supersede_date_decision(monkeypatch,db):
    history(db);row=item();source(monkeypatch,snapshot([row]));first=decide(db,row);db.commit()
    with pytest.raises(HTTPException):
        notes.append(db,1,'shop','ro-1',ReconciliationNoteInput(note='Narrative cannot invalidate date review.',supersedes_note_id=first['id']),'bad','owner')


def test_legacy_note_idempotency_digest_still_replays_after_upgrade(db):
    from datetime import datetime, timezone
    from app.models.dieselbridge_reconciliation import DieselBridgeReconciliationNote as Note
    history(db)
    body=ReconciliationNoteInput(note='Old note remains reference only.',confirmed_service_date='2026-07-13')
    identity=dict(tenant_id=1,slug='shop',shop_id='shop-1',customer_id='customer-1',repair_order_id='ro-1')
    legacy_body=body.model_dump(mode='json',exclude={'date_treatment','expected_source_revision'})
    values=body.model_dump(exclude={'date_treatment','expected_source_revision'})
    old=Note(**identity,**values,key='old-note',request_digest=financial.digest({'scope':identity,'body':legacy_body,'author':'owner'}),author='owner',created_at=datetime.now(timezone.utc).isoformat())
    db.add(old);db.commit()
    assert notes.append(db,1,'shop','ro-1',body,'old-note','owner')['id']==old.id
