"""Owner reconciliation evidence survives financial sync without becoming financial facts."""
import asyncio
from datetime import date
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from app.models.dieselbridge import DieselBridgeRepairHistory, DieselBridgeRepairLink
from app.models.dieselbridge_reconciliation import DieselBridgeReconciliationNote
from app.models.finance import FinanceEvent
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.schemas.dieselbridge_financial import ReconciliationNoteInput
from app.services import dieselbridge_reconciliation as notes
from tests.test_dieselbridge_financial import setup, source, snapshot, item, sync


def history(db,ro='ro-1',customer='customer-1',tenant=1):
    row=DieselBridgeRepairHistory(tenant_id=tenant,shop_id='shop-1',customer_id=customer,repair_order_id=ro,revision='old',payload={},truck_id=1,state='active',review_reason='matched')
    db.add(row);db.commit();return row


def body(**changes):
    return ReconciliationNoteInput(note='Owner confirms the same historical job.',source_references=['DBN INV-21','ETSINV-1183'],confirmed_service_date='2026-07-13',original_invoice_date='2026-08-04',amount_discrepancy='DBN1072.05 versus ETS1089.21; difference17.16 unexplained.',**changes)


def test_preimport_note_survives_import_replay_and_source_review(monkeypatch,db):
    history(db)
    saved=notes.append(db,1,'shop','ro-1',body(),'note-1','verified-owner')
    db.commit()
    assert db.query(Repair).count()==db.query(FinanceEvent).count()==db.query(RepairReserveLedger).count()==0
    source(monkeypatch,snapshot([item()]));sync(db);db.commit()
    link=db.query(DieselBridgeRepairLink).one()
    state=__import__('app.services.dieselbridge_financial',fromlist=['public_state']).public_state(db,1,link)
    assert state['reconciliation_notes']==[saved] and not state['reconciliation_notes_has_older']
    assert db.query(Repair).one().repair_date==date(2026,10,1) # note does not silently override source
    sync(db,'repeat');source(monkeypatch,snapshot([item(total='1200.00')]));sync(db,'changed');db.commit()
    source(monkeypatch,snapshot([]));sync(db,'removed');db.commit()
    assert notes.for_link(db,1,link)['reconciliation_notes']==[saved]
    assert db.query(DieselBridgeReconciliationNote).count()==1
    assert db.query(RepairReserveLedger).count()==0


def test_retry_is_exact_and_correction_retains_original(db):
    history(db)
    first=notes.append(db,1,'shop','ro-1',body(),'retry','owner');db.commit()
    assert notes.append(db,1,'shop','ro-1',body(),'retry','owner')==first
    corrected=notes.append(db,1,'shop','ro-1',body(supersedes_note_id=first['id']),'correction','owner');db.commit()
    assert corrected['supersedes_note_id']==first['id']
    assert notes.page(db,1,'shop','ro-1')['items']==[first,corrected]
    with pytest.raises(HTTPException) as exc:
        notes.append(db,1,'shop','ro-1',ReconciliationNoteInput(note='Different decision'),'retry','owner')
    assert exc.value.status_code==409
    assert db.query(DieselBridgeReconciliationNote).count()==2


def test_note_scope_missing_other_customer_and_cross_ro_correction_fail(db):
    with pytest.raises(HTTPException):notes.append(db,1,'shop','absent',body(),'one','owner')
    history(db,customer='other-customer')
    with pytest.raises(HTTPException):notes.append(db,1,'shop','ro-1',body(),'two','owner')
    history(db,ro='ro-2');first=notes.append(db,1,'shop','ro-2',body(),'three','owner');db.commit()
    history(db,ro='ro-3')
    with pytest.raises(HTTPException):notes.append(db,1,'shop','ro-3',body(supersedes_note_id=first['id']),'four','owner')
    assert db.query(DieselBridgeReconciliationNote).count()==1


def test_notes_append_only_even_via_sql_and_failed_transaction_rolls_back(db):
    history(db);first=notes.append(db,1,'shop','ro-1',body(),'one','owner');db.commit()
    row=db.query(DieselBridgeReconciliationNote).one();row.note='Overwrite'
    with pytest.raises(ValueError,match='immutable'):db.flush()
    db.rollback()
    for statement in ['UPDATE dbn_reconciliation_notes SET note=\'overwrite\'','DELETE FROM dbn_reconciliation_notes']:
        with pytest.raises(DatabaseError):db.execute(text(statement))
        db.rollback()
    assert notes.page(db,1,'shop','ro-1')['items']==[first]
    notes.append(db,1,'shop','ro-1',body(),'rolled-back','owner');db.rollback()
    assert db.query(DieselBridgeReconciliationNote).count()==1


def test_authenticated_routes_reject_spoofing_and_keep_notes_when_financial_disabled(monkeypatch,db,client):
    history(db);monkeypatch.delenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED')
    url='/api/v1/accounting/dieselbridge/connections/shop/repair-orders/ro-1/reconciliation-notes'
    headers={'X-Tenant-ID':'1','Idempotency-Key':'route-note'}
    payload=body().model_dump(mode='json')
    assert client.post(url,json={**payload,'author':'spoof'},headers=headers).status_code==422
    response=client.post(url,json=payload,headers=headers)
    assert response.status_code==200 and response.json()['author']!='spoof'
    assert client.post(url,json=payload,headers=headers).json()==response.json()
    assert client.get(url,headers={'X-Tenant-ID':'2'}).status_code==404
    assert client.get(url).status_code==400
    assert client.get(url,headers=headers).json()['items']==[response.json()]
    assert db.query(Repair).count()==db.query(FinanceEvent).count()==db.query(RepairReserveLedger).count()==0


def test_pagination_and_same_tenant_other_ro_do_not_mix(db):
    history(db);history(db,ro='ro-2')
    for i in range(3):notes.append(db,1,'shop','ro-1',body(),str(i),'owner')
    notes.append(db,1,'shop','ro-2',body(),'other','owner');db.commit()
    first=notes.page(db,1,'shop','ro-1',limit=2)
    second=notes.page(db,1,'shop','ro-1',after=first['next_after'],limit=2)
    assert len(first['items'])==2 and len(second['items'])==1 and second['next_after'] is None
    assert all(x['repair_order_id']=='ro-1' for x in first['items']+second['items'])


def test_corrected_note_cannot_be_corrected_twice_and_connection_scope_is_pinned(monkeypatch,db):
    import json
    from tests.test_dieselbridge_financial import C
    history(db)
    first=notes.append(db,1,'shop','ro-1',body(),'first','owner');db.commit()
    notes.append(db,1,'shop','ro-1',body(supersedes_note_id=first['id']),'second','owner');db.commit()
    with pytest.raises(HTTPException) as exc:
        notes.append(db,1,'shop','ro-1',body(supersedes_note_id=first['id']),'third','owner')
    assert exc.value.detail['code']=='NOTE_ALREADY_CORRECTED'
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS',json.dumps([{**C,'bill_to_id':'other-customer'}]))
    with pytest.raises(HTTPException) as exc:notes.page(db,1,'shop','ro-1')
    assert exc.value.detail['code']=='CONNECTION_SCOPE_CHANGED'


def test_tile_summary_bounded_and_complete_history_paginated(monkeypatch,db,client):
    history(db)
    for i in range(101):notes.append(db,1,'shop','ro-1',body(),str(i),'owner')
    db.commit();source(monkeypatch,snapshot([item()]));sync(db);db.commit()
    link=db.query(DieselBridgeRepairLink).one()
    state=notes.for_link(db,1,link)
    assert len(state['reconciliation_notes'])==100 and state['reconciliation_notes_has_older']
    assert state['reconciliation_notes'][0]['id']==2
    url=f'/api/v1/accounting/dieselbridge/repairs/{link.repair_id}/reconciliation-notes'
    response=client.get(url,headers={'X-Tenant-ID':'1'})
    assert len(response.json()['items'])==100 and response.json()['next_after']==100
    response=client.post(url,headers={'X-Tenant-ID':'1','Idempotency-Key':'repair-route'},json=body().model_dump(mode='json'))
    assert response.status_code==200 and response.json()['repair_order_id']=='ro-1'
    assert client.get(url.replace(str(link.repair_id),'999'),headers={'X-Tenant-ID':'1'}).status_code==404
