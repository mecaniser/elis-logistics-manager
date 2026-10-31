import asyncio
from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.models.repair import Repair
from app.models.truck import Truck
from app.models.dieselbridge import DieselBridgeRepairLink as Link, DieselBridgeFinancialOperation as Operation
from app.models.repair_reserve_ledger import RepairReserveLedger as Reserve
from app.models.journal_entry import JournalEntry as Journal
from app.models.journal_entry_line import JournalEntryLine as Line
from app.schemas.dieselbridge_financial import TemporaryReplacementPreview as Preview, TemporaryReplacementApply as Apply, TemporaryReplacementRestorePreview as RestorePreview, TemporaryReplacementRestore as Restore
from app.services import dieselbridge_replacements as r
from app.services.accounting_service import create_repair_journal_entry
from tests.test_dieselbridge_financial import setup, source, snapshot, item, sync


@pytest.fixture
def seeded(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db)
    target=db.query(Link).one().repair_id
    old=Repair(truck_id=1,repair_date=date(2026,3,30),title='Temporary cleaning',cost=Decimal('150.00'),paid_from_reserve=True,receipt_path='preserve-this-receipt')
    db.add(old);db.flush()
    withdrawal=Reserve(tenant_id=1,truck_id=1,entry_date=old.repair_date,entry_type='withdrawal',amount=old.cost,source_type='repair',source_id=old.id)
    db.add(withdrawal);create_repair_journal_entry(db,old,auto_commit=False);db.commit()
    return target,old.id,withdrawal.id


def review(db,ids):
    return asyncio.run(r.preview(db,1,'shop',Preview(repair_order_id='ro-1',legacy_repair_ids=ids,correction_date='2026-10-22')))


def apply(db,ids,key='replace',**changes):
    plan=review(db,ids)
    args=dict(repair_order_id='ro-1',legacy_repair_ids=ids,correction_date='2026-10-22',expected_plan_digest=plan['plan_digest'],confirmed_same_job=True,reviewed_existing_effects=True,reason='Owner reviewed same job and existing entries')
    args.update(changes)
    return asyncio.run(r.apply(db,1,'shop',Apply(**args),key))


def test_preview_read_only_and_exact_effects(db,seeded):
    target,old,wid=seeded
    counts=[db.query(m).count() for m in (Operation,Reserve,Journal,Line)]
    p=review(db,[old])
    assert p['expense_removed']==p['reserve_correction']=='150.00'
    assert p['temporary_records'][0]['withdrawals'][0]['id']==str(wid)
    assert p['payment_created'] is False
    assert counts==[db.query(m).count() for m in (Operation,Reserve,Journal,Line)]
    assert db.get(Repair,old).archived_at is None


def test_apply_retains_evidence_and_reverses_exactly_once(db,seeded):
    target,old,wid=seeded;p=review(db,[old])
    body=Apply(repair_order_id='ro-1',legacy_repair_ids=[old],correction_date='2026-10-22',expected_plan_digest=p['plan_digest'],confirmed_same_job=True,reviewed_existing_effects=True,reason='Owner confirmed temporary duplicate')
    first=asyncio.run(r.apply(db,1,'shop',body,'same'));db.commit()
    assert asyncio.run(r.apply(db,1,'shop',body,'same'))==first
    archived=db.query(Repair).filter_by(id=old).execution_options(include_archived_repairs=True).one()
    assert archived.replaced_by_repair_id==target and archived.receipt_path=='preserve-this-receipt' and archived.cost==Decimal('150.00')
    assert db.query(Reserve).filter_by(reversal_of_id=wid).count()==1
    original=db.query(Journal).filter_by(reference_type='repair',reference_id=old).one()
    reverse=db.query(Journal).filter_by(reference_type='dbn_temp_reverse',reference_id=original.id).one()
    assert [(x.account_id,x.debit,x.credit) for x in db.query(Line).filter_by(journal_entry_id=reverse.id).order_by(Line.id)]==[(x.account_id,x.credit,x.debit) for x in db.query(Line).filter_by(journal_entry_id=original.id).order_by(Line.id)]
    assert db.query(Repair).filter_by(id=old).count()==0
    assert db.query(Reserve).filter_by(source_type='dbn_payment').count()==0


def test_restore_is_compensating_retains_originals_and_retry_safe(db,seeded):
    target,old,wid=seeded;result=apply(db,[old]);db.commit();db.expire_all()
    p=asyncio.run(r.restore_preview(db,1,'shop',result['operation_id'],RestorePreview(correction_date='2026-10-23')))
    body=Restore(correction_date='2026-10-23',expected_plan_digest=p['plan_digest'],reviewed_existing_effects=True,reason='Reviewed undo of temporary replacement')
    undone=asyncio.run(r.restore(db,1,'shop',result['operation_id'],body,'undo'));db.commit()
    assert asyncio.run(r.restore(db,1,'shop',result['operation_id'],body,'undo'))==undone
    assert db.query(Repair).filter_by(id=old).one().archived_at is None
    assert db.query(Reserve).filter_by(source_type='dbn_temp_restore').one().amount==Decimal('150.00')
    assert db.get(Reserve,wid) is not None and db.query(Journal).filter_by(reference_type='dbn_temp_restore').count()==1
    with pytest.raises(HTTPException):asyncio.run(r.restore_preview(db,1,'shop',result['operation_id'],RestorePreview(correction_date='2026-10-23')))


def test_no_cost_or_withdrawal_is_inferred_from_reserve_flag(db,seeded):
    old=Repair(truck_id=1,repair_date=date(2026,3,21),title='Not charged NOX',cost=None,paid_from_reserve=True)
    db.add(old);db.commit();result=apply(db,[old.id])
    assert result['plan']['expense_removed']==result['plan']['reserve_correction']=='0.00'
    assert not result['corrections'][0]['reserve_reversals'] and not result['corrections'][0]['journal_reversals']


@pytest.mark.parametrize('change',[{'confirmed_same_job':False},{'reviewed_existing_effects':False},{'expected_plan_digest':'0'*64}])
def test_review_or_stale_plan_rejected_without_archive(db,seeded,change):
    with pytest.raises(HTTPException):apply(db,[seeded[1]],**change)
    assert db.get(Repair,seeded[1]).archived_at is None


def test_changed_source_cannot_replace(db,monkeypatch,seeded):
    source(monkeypatch,snapshot([item(total='2000.00')]))
    with pytest.raises(HTTPException):review(db,[seeded[1]])


def test_unsupported_finance_claim_requires_separate_review(db,seeded):
    from app.models.finance import FinanceEvent
    db.add(FinanceEvent(id='claim',tenant_id=1,sequence=99,key='claim',kind='memo',effective_date=date(2026,3,30),payload={'legacy_repair_id':seeded[1]},digest='a'*64));db.flush()
    with pytest.raises(HTTPException):review(db,[seeded[1]])


def test_no_cross_asset_or_duplicate_ids(db,seeded):
    with pytest.raises(HTTPException):review(db,[seeded[1],seeded[1]])
    db.add(Truck(id=2,tenant_id=1,name='Other',vin='VINOTHER',vehicle_type='truck'));db.flush()
    old=Repair(truck_id=2,repair_date=date(2026,3,1),cost=10);db.add(old);db.flush()
    with pytest.raises(HTTPException):review(db,[old.id])


def test_disabled_apply_leaves_all_records(db,monkeypatch,seeded):
    monkeypatch.delenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED')
    with pytest.raises(HTTPException):apply(db,[seeded[1]])
    assert db.get(Repair,seeded[1]).archived_at is None


def test_correction_cannot_precede_original_effects(db,seeded):
    with pytest.raises(HTTPException):
        asyncio.run(r.preview(db,1,'shop',Preview(repair_order_id='ro-1',legacy_repair_ids=[seeded[1]],correction_date='2026-01-01')))


def test_changed_legacy_amount_invalidates_plan(db,seeded):
    p=review(db,[seeded[1]])
    db.get(Repair,seeded[1]).cost=Decimal('160.00');db.flush()
    with pytest.raises(HTTPException):apply(db,[seeded[1]],expected_plan_digest=p['plan_digest'])


def test_restored_record_cannot_enter_legacy_edit_delete(db,seeded):
    from app.routers.repairs import require_manual_repair
    result=apply(db,[seeded[1]]);db.commit()
    p=asyncio.run(r.restore_preview(db,1,'shop',result['operation_id'],RestorePreview(correction_date='2026-10-23')))
    body=Restore(correction_date='2026-10-23',expected_plan_digest=p['plan_digest'],reviewed_existing_effects=True,reason='Reviewed restoration')
    asyncio.run(r.restore(db,1,'shop',result['operation_id'],body,'restore'))
    with pytest.raises(HTTPException):require_manual_repair(db,db.get(Repair,seeded[1]),1)


def test_changed_original_effect_blocks_restore(db,seeded):
    result=apply(db,[seeded[1]]);db.commit()
    db.get(Reserve,seeded[2]).amount=Decimal('151.00');db.flush()
    with pytest.raises(HTTPException):asyncio.run(r.restore_preview(db,1,'shop',result['operation_id'],RestorePreview(correction_date='2026-10-23')))


def test_closed_original_period_blocks_replacement(db,seeded):
    from app.models.finance import FinanceEvent
    db.add(FinanceEvent(tenant_id=1,key='closed',kind='close_period',effective_date=date(2026,4,1),payload={'start':'2026-03-01','end':'2026-03-31'},digest='c'*64));db.flush()
    with pytest.raises(HTTPException):review(db,[seeded[1]])


def test_http_review_archive_audit_restore_and_legacy_guard(client,db,seeded):
    client.headers['X-Tenant-ID']='1'
    prefix='/api/v1/accounting/dieselbridge/connections/shop/financial-import'
    body={'repair_order_id':'ro-1','legacy_repair_ids':[seeded[1]],'correction_date':'2026-10-22'}
    p=client.post(prefix+'/archive-preview',json=body)
    assert p.status_code==200,p.text
    applied=client.post(prefix+'/archive-apply',json={**body,'expected_plan_digest':p.json()['plan_digest'],'confirmed_same_job':True,'reviewed_existing_effects':True,'reason':'Owner reviewed exact temporary duplicate'},headers={'Idempotency-Key':'http-replace'})
    assert applied.status_code==200,applied.text
    op=applied.json()['operation_id']
    assert client.get(prefix+f'/replacements/{op}').status_code==200
    p=client.post(prefix+f'/replacements/{op}/restore-preview',json={'correction_date':'2026-10-23'})
    assert p.status_code==200,p.text
    undo=client.post(prefix+f'/replacements/{op}/restore',json={'correction_date':'2026-10-23','expected_plan_digest':p.json()['plan_digest'],'reviewed_existing_effects':True,'reason':'Explicit reviewed undo'},headers={'Idempotency-Key':'http-undo'})
    assert undo.status_code==200,undo.text
    assert client.delete('/api/repairs/'+str(seeded[1])).status_code==409
    assert client.put('/api/repairs/'+str(seeded[1]),data={'repair_update_json':'{"cost":999}'}).status_code==409
    manual=client.post('/api/accounting/journal-entries',json={'entry_date':'2026-10-23','reference_type':'repair','reference_id':seeded[1],'lines':[]})
    assert manual.status_code==409
    fake=client.post('/api/accounting/journal-entries',json={'entry_date':'2026-10-23','reference_type':'dbn_temp_reverse','reference_id':1,'lines':[]})
    assert fake.status_code==409
    from app.services.dieselbridge_financial import public_state
    state=public_state(db,1,db.query(Link).one())
    assert state['temporary_replacements'][0]['restored'] is True


def test_restore_closed_period_and_original_chronology(db,seeded):
    from app.models.finance import FinanceEvent
    result=apply(db,[seeded[1]]);db.commit()
    with pytest.raises(HTTPException):asyncio.run(r.restore_preview(db,1,'shop',result['operation_id'],RestorePreview(correction_date='2026-10-21')))
    db.add(FinanceEvent(tenant_id=1,key='closed-restoration',kind='close_period',effective_date=date(2026,10,24),payload={'start':'2026-10-22','end':'2026-10-23'},digest='d'*64));db.flush()
    with pytest.raises(HTTPException):asyncio.run(r.restore_preview(db,1,'shop',result['operation_id'],RestorePreview(correction_date='2026-10-24')))


def test_three_null_cost609_placeholders_archive_once_and_protect_other_jobs(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db)
    canonical=db.query(Link).one().repair_id
    old=[Repair(truck_id=1,repair_date=date(2026,4,20),title=title,cost=None,paid_from_reserve=False) for title in ['Temporary bearings','Temporary steering','Temporary tires']]
    cleaning=Repair(truck_id=1,repair_date=date(2026,4,20),title='Separate cleaning',cost=Decimal('150.00'),paid_from_reserve=False)
    diagnostic=Repair(truck_id=1,repair_date=date(2026,4,20),title='Separate diagnostic',cost=Decimal('202.80'),paid_from_reserve=False)
    db.add_all([*old,cleaning,diagnostic]);db.commit();ids=[r.id for r in old]
    first=apply(db,ids);db.commit();sync(db,'repeat-source');db.commit()
    assert db.query(Repair).count()==3
    assert {r.id for r in db.query(Repair).all()}=={canonical,cleaning.id,diagnostic.id}
    archived=db.query(Repair).filter(Repair.id.in_(ids)).execution_options(include_archived_repairs=True).all()
    assert len(archived)==3 and all(r.replaced_by_repair_id==canonical and r.cost is None for r in archived)
    assert db.query(Reserve).count()==0
    assert first['operation_id']
