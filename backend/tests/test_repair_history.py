from datetime import date
import pytest
from fastapi import HTTPException
from app.models.repair import Repair
from app.models.truck import Truck
from app.models.tenant import Tenant
from app.services.repair_history import repair_history
from tests.test_finance import truck, cmd, policy_setup, ASOF


def repair(db, truck, **kw):
    r = Repair(truck_id=truck.id, repair_date=ASOF, title='Repair', cost='500.00', **kw)
    db.add(r); db.commit(); return r


def test_no_payment_or_reserve_inference(db, truck):
    r = repair(db, truck, paid_from_reserve=True)
    row = repair_history(db, 1, ASOF)['rows'][0]
    assert row['payment_status'] == 'unverified'
    assert row['recorded_vendor_outstanding'] is None
    assert 'legacy_reserve_flag_needs_funding_evidence' in row['issues']
    assert not row['automatic_posting_allowed']


def test_personal_partial_payment_substitutes_claim_and_blocks_duplicate(db, truck):
    r = repair(db, truck); d = policy_setup(db)
    b = cmd(db, 'bill', legacy_repair_id=r.id, evidence_id=d, source_ref='repair-one', description='Repair', amount='500.00', category='repairs', asset_id=truck.id)
    p = cmd(db, 'payment', claim_id=b.id, amount='200.00', payer='owner', evidence_id=d)
    row = repair_history(db, 1, ASOF)['rows'][0]
    assert row['recorded_vendor_outstanding'] == '300.00'
    assert row['recorded_owner_reimbursement'] == '200.00'
    assert row['payment_event_ids'] == [p.id]
    with pytest.raises(HTTPException) as exc:
        cmd(db, 'owner_advance', legacy_repair_id=r.id, evidence_id=d, source_ref='duplicate', description='Duplicate', amount='500.00', category='repairs', asset_id=truck.id)
    assert exc.value.detail['code'] == 'DUPLICATE_REPAIR'


def test_cross_business_repair_link_rejected(db, truck):
    db.add(Tenant(id=2,name='Other',business_type='logistics')); db.commit()
    other = Truck(name='Other', tenant_id=2, vehicle_type='truck'); db.add(other); db.commit()
    r = repair(db,other); d=policy_setup(db)
    assert repair_history(db,1,ASOF)['rows'] == []
    with pytest.raises(HTTPException) as exc:
        cmd(db,'bill',legacy_repair_id=r.id,evidence_id=d,source_ref='foreign',description='Repair',amount='500.00',category='repairs',asset_id=truck.id)
    assert exc.value.status_code == 404


def test_asof_excludes_future_repairs_and_route_enforces_scope(db, truck, client, monkeypatch):
    repair(db,truck)
    assert repair_history(db,1,date(2026,9,20))['rows'] == []
    monkeypatch.setenv('APP_AUTH_TENANT_IDS','1'); monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS','1')
    assert client.get('/api/v1/accounting/repair-history',params={'as_of':'2026-09-21'},headers={'X-Tenant-ID':'1'}).status_code == 200
    assert client.get('/api/v1/accounting/repair-history',params={'as_of':'2026-09-21'},headers={'X-Tenant-ID':'2'}).status_code == 404


def test_optional_repair_link_preserves_old_command_idempotency(db, truck):
    from app.models.finance import FinanceEvent
    from app.schemas.finance import Command
    from app.services import finance as f
    d = policy_setup(db)
    command = Command(effective_date=ASOF, payload={'kind':'bill','evidence_id':d,'source_ref':'old-bill','description':'Existing','amount':'500.00','category':'repairs','asset_id':truck.id})
    old_data = command.model_dump(mode='json'); old_data['payload'].pop('legacy_repair_id')
    event = FinanceEvent(tenant_id=1,key='old-command-key',digest=f.digest(old_data),kind='bill',effective_date=ASOF,payload=old_data['payload'])
    db.add(event);db.commit()
    assert f.append_command(db,1,command,'old-command-key').id == event.id


def test_metadata_views_do_not_fetch_original_invoice_bytes(db, truck):
    from sqlalchemy import event
    from tests.test_finance import doc
    from app.routers.finance import list_evidence
    repair(db, truck)
    evidence_id = doc(db, b'large preserved invoice content')
    db.expire_all()
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('SELECT'):
            statements.append(statement)
    event.listen(db.bind, 'before_cursor_execute', capture)
    try:
        result = repair_history(db, 1, ASOF)
        evidence = list_evidence(limit=100, cursor=None, db=db, tenant=1)
        assert result['rows'][0]['recorded_cost'] == '500.00'
        assert evidence['items'][0]['id'] == evidence_id
        assert not any('content_base64' in statement for statement in statements)
    finally:
        event.remove(db.bind, 'before_cursor_execute', capture)
