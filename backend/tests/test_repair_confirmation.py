from datetime import date
import pytest
from fastapi import HTTPException
from app.models.finance import FinanceEvidence, FinanceEvent, FinancePosting
from app.schemas.repair_review import RepairConfirmation
from app.services.repair_confirmation import save_confirmation
from app.services.repair_history import repair_history
from tests.test_repair_history import repair
from tests.test_finance import truck, ASOF


def payload(db, **kw):
    row = repair_history(db, 1, date.today())['rows'][0]
    return RepairConfirmation(items=[{'repair_id': row['legacy_id'], 'snapshot': row['review_snapshot'], 'previous_id': row['confirmation']['id'] if row['confirmation'] else None}], status='paid', method='cash', source='unknown', **kw)


def test_confirmation_is_evidence_not_payment_or_expense(db, truck):
    repair(db, truck)
    request = payload(db)
    result = save_confirmation(db, 1, request); db.commit()
    assert save_confirmation(db, 1, request) == result
    row = repair_history(db, 1, ASOF)['rows'][0]
    assert row['confirmation']['paid_amount'] == '500.00'
    assert row['confirmation']['source'] == 'unknown'
    assert row['confirmation']['paid_date'] is None
    assert row['payment_status'] == 'unverified'
    assert row['recorded_vendor_outstanding'] is None
    assert db.query(FinanceEvent).count() == db.query(FinancePosting).count() == 0
    assert db.query(FinanceEvidence).count() == 1


def test_corrections_preserved_and_stale_writer_rejected(db, truck):
    repair(db, truck)
    request = payload(db)
    first = save_confirmation(db, 1, request); db.commit()
    correction = payload(db, note='Receipt checked')
    save_confirmation(db, 1, correction); db.commit()
    assert db.query(FinanceEvidence).count() == 2
    assert db.query(FinanceEvidence).filter_by(supersedes_id=first['ids'][0]).count() == 1
    with pytest.raises(HTTPException):
        save_confirmation(db, 1, request.model_copy(update={'note': 'Stale change'}))


def test_changed_repair_invalidates_confirmation(db, truck):
    r = repair(db, truck); request = payload(db)
    save_confirmation(db, 1, request); db.commit()
    r.cost = '600.00'; db.commit()
    assert repair_history(db, 1, ASOF)['rows'][0]['confirmation']['stale']
    with pytest.raises(HTTPException): save_confirmation(db, 1, request)


def test_other_business_and_missing_repair_rejected(db, truck):
    from app.models.tenant import Tenant
    db.add(Tenant(id=2, name='Other', business_type='logistics')); db.commit()
    repair(db, truck); request = payload(db)
    with pytest.raises(HTTPException): save_confirmation(db, 2, request)
    assert db.query(FinanceEvidence).count() == 0


def test_batch_without_matching_invoices_is_blocked(db, truck):
    repair(db, truck); repair(db, truck)
    rows = repair_history(db, 1, ASOF)['rows']
    request = RepairConfirmation(items=[{'repair_id':r['legacy_id'], 'snapshot':r['review_snapshot']} for r in rows], status='paid')
    with pytest.raises(HTTPException): save_confirmation(db, 1, request)
    assert db.query(FinanceEvidence).count() == 0


def test_partial_bounds_and_unpaid_details(db, truck):
    repair(db, truck)
    request = payload(db)
    with pytest.raises(HTTPException): save_confirmation(db, 1, request.model_copy(update={'status':'partial','paid_amount':600}))
    with pytest.raises(HTTPException): save_confirmation(db, 1, request.model_copy(update={'status':'unpaid'}))


def test_route_requires_authorized_business(db, truck, client, monkeypatch):
    repair(db, truck)
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS','1')
    monkeypatch.setenv('APP_AUTH_TENANT_IDS','1')
    data = payload(db).model_dump(mode='json')
    assert client.post('/api/v1/accounting/repair-confirmations',json=data,headers={'X-Tenant-ID':'2'}).status_code == 404
    assert client.post('/api/v1/accounting/repair-confirmations',json=data,headers={'X-Tenant-ID':'1'}).status_code == 200


def test_matching_batch_is_atomic_and_idempotent(db, truck):
    import base64, hashlib
    for n in range(2):
        r = repair(db, truck)
        content = str(n).encode()
        db.add(FinanceEvidence(tenant_id=1, sha256=hashlib.sha256(content).hexdigest(), filename='invoice.pdf', media_type='application/pdf', content_base64=base64.b64encode(content).decode(), source_key=f'invoice:{n}', extraction_version='test', extracted={'legacy_repair_ids':[r.id], 'invoice_review':{'source_total':'500.00'}}))
        db.commit()
    rows = repair_history(db,1,ASOF)['rows']
    request = RepairConfirmation(items=[{'repair_id':r['legacy_id'],'snapshot':r['review_snapshot']} for r in rows],status='paid',method='cash')
    first = save_confirmation(db,1,request);db.commit()
    assert save_confirmation(db,1,request) == first
    assert db.query(FinanceEvidence).count() == 4
    assert db.query(FinancePosting).count() == 0


def test_uploaded_original_preserved_atomically(db, truck, client, monkeypatch, tmp_path):
    import base64
    from app.routers import repairs
    monkeypatch.setattr(repairs, 'UPLOAD_DIR', str(tmp_path))
    monkeypatch.setattr(repairs, 'parse_repair_invoice_pdf', lambda path: {'repair_date':ASOF,'cost':500,'description':'Repair','title':'Repair','invoice_number':'unique-test'})
    monkeypatch.setattr(repairs, 'upload_pdf', lambda *args, **kwargs: None)
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS','1')
    content = b'%PDF-test original bytes'
    response = client.post('/api/repairs/upload',headers={'X-Tenant-ID':'1'}, data={'truck_id':str(truck.id)}, files={'file':('test.pdf', content,'application/pdf')})
    assert response.status_code == 200, response.text
    evidence = db.query(FinanceEvidence).one()
    assert base64.b64decode(evidence.content_base64) == content
    assert evidence.extracted['legacy_repair_ids'] == [response.json()['repair']['id']]
    assert evidence.extracted['payment_basis'] == 'not_established'
