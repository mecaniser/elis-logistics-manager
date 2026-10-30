import json
from copy import deepcopy
from datetime import date, timedelta
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import HTTPException
from app.models.dieselbridge import DieselBridgeConnection as Connection, DieselBridgeInvoice as Invoice
from app.models.truck import Truck
from app.models.tenant import Tenant
from app.models.repair import Repair
from app.models.finance import FinanceEvidence, FinanceEvent, FinancePosting
from app.models.journal_entry import JournalEntry
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.services import dieselbridge as d
from app.services.repair_history import repair_history

C = {'slug': 'shop', 'tenant_id': 1, 'shop_id': 'shop-1', 'bill_to_id': 'customer-1', 'base_url': 'https://dieselbridge.example', 'api_key_env': 'TEST_DB094_KEY'}
BASE = '/api/v1/accounting/dieselbridge'
H = {'X-Tenant-ID': '1'}
VIN = '1M8GDM9AXKP042788'

def item(**kw):
    return {'shop_id': 'shop-1', 'invoice_id': 'inv-1', 'invoice_number': 'INV-001', 'repair_order_id': 'ro-1', 'vehicle_id': 'v-1', 'vin': VIN, 'unit_number': '603', 'mileage_in': 123456, 'mileage_in_carried': True, 'invoice_date': '2026-09-01', 'effective_updated_at': '2026-09-02T12:00:00+00:00', 'status': 'paid', 'voided_at': None, 'supersedes_invoice_id': None, 'total_amount': '500.00', 'currency': 'USD', 'line_items': {'labor': [{'description': 'Engine repair'}], 'parts': []}, **kw}

@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.delenv('APP_AUTH_USERNAME', raising=False)
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS', '1')
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS', json.dumps([C]))
    monkeypatch.setenv('TEST_DB094_KEY', 'fixture-only-token')

@pytest.fixture
def truck(db):
    t = Truck(name='603', tenant_id=1, vehicle_type='truck', vin=VIN.lower())
    db.add(t); db.commit(); return t

def stage(db, data=None):
    row = d.stage(db, 1, C, data or item()); db.commit(); return row

def page_mock(monkeypatch, values, cursor=None):
    async def fetch(self, params): return {'items': values, 'next_cursor': cursor, 'watermark': params['updated_before']}
    monkeypatch.setattr(d.SourceClient, 'page', fetch)

def accept(client, row, **kw):
    return client.post(f'{BASE}/invoices/{row.id}/accept', headers=H, json={'revision': row.revision, 'cost_treatment': 'repair_expense', 'note': 'Reviewed invoice and confirmed repair expense.', **kw})

def test_unique_vin_tenant_scope_and_later_trucks(db, truck):
    db.add(Tenant(id=2, name='Other', business_type='logistics')); db.flush()
    db.add(Truck(name='Other', tenant_id=2, vehicle_type='truck', vin=VIN)); db.commit()
    row = stage(db, item(vin=' '+VIN.lower()+' '))
    assert row.truck_id == truck.id and row.state == 'review_required'
    for n in range(4): db.add(Truck(name=f'Later {n}', tenant_id=1, vehicle_type='truck', vin=f'LATER{n}'))
    db.commit()
    assert stage(db, item(invoice_id='later', vin='LATER3')).truck_id is not None
    assert db.query(Repair).count() == 0

@pytest.mark.parametrize('vin,kind,expected', [('', 'truck', 'missing_vin'), ('OTHER', 'truck', 'unmatched_vin'), (VIN, 'trailer', 'vehicle_type_mismatch'), (VIN, 'suv', 'vehicle_type_mismatch')])
def test_unmatched_vehicle_no_expenses(db, client, vin, kind, expected):
    db.add(Truck(name='Asset', tenant_id=1, vehicle_type=kind, vin=VIN)); db.commit()
    row = stage(db, item(vin=vin))
    assert row.review_reason == expected and accept(client, row).status_code == 409
    assert db.query(Repair).count() == 0

def test_duplicate_vins_rechecked_at_accept(db, truck, client):
    row = stage(db)
    db.add(Truck(name='Duplicate', tenant_id=1, vehicle_type='truck', vin=VIN)); db.commit()
    assert accept(client, row).status_code == 409
    assert stage(db, item(invoice_id='dup')).review_reason == 'duplicate_vin'

def test_accept_idempotent_paid_never_infers_payment(db, truck, client):
    row = stage(db)
    assert accept(client, row).status_code == accept(client, row).status_code == 200
    repair = db.query(Repair).one()
    assert repair.truck_id == truck.id and not repair.paid_from_reserve and repair.miles is None
    assert db.query(FinanceEvidence).count() == 1
    for model in (FinanceEvent, FinancePosting, JournalEntry, RepairReserveLedger): assert db.query(model).count() == 0
    h = repair_history(db, 1, date(2026, 9, 30))['rows'][0]
    assert h['payment_status'] == 'unverified' and h['recorded_vendor_outstanding'] is None

def test_revision_replay_correction_preserves_accepted_expense(db, truck, client):
    row = stage(db); assert accept(client, row).status_code == 200
    source = deepcopy(row.payload); stage(db, source); assert row.state == 'accepted'
    stage(db, item(effective_updated_at='2026-09-03T00:00:00Z', total_amount='700.00'))
    stage(db, source)
    assert row.state == 'correction_required' and str(db.query(Repair).one().cost) == '500.00'
    assert row.revision == '2026-09-03T00:00:00+00:00' and accept(client, row).status_code == 409
    h = repair_history(db, 1, date(2026, 9, 30))['rows'][0]
    assert 'dieselbridge_correction_required' in h['issues'] and not h['batch_eligible']
    assert h['owner_posting']['status'] == 'review_required'

def test_changed_vin_never_remaps(db, truck, client):
    row = stage(db); assert accept(client, row).status_code == 200
    db.add(Truck(name='Other', tenant_id=1, vehicle_type='truck', vin='OTHER')); db.commit()
    stage(db, item(vin='OTHER', effective_updated_at='2026-09-04T00:00:00Z'))
    assert row.truck_id == truck.id and row.review_reason == 'truck_identity_changed'
    assert db.query(Repair).one().truck_id == truck.id

@pytest.mark.parametrize('change', [{'status': 'cancelled'}, {'voided_at': '2026-09-03T00:00:00Z'}, {'supersedes_invoice_id': 'old'}])
def test_cancel_void_replacement_held(db, truck, client, change):
    assert accept(client, stage(db, item(**change))).status_code == 409

def test_supersession_reverse_arrival(db, truck, client):
    new = stage(db, item(invoice_id='new', supersedes_invoice_id='inv-1'))
    old = stage(db)
    assert old.state == 'correction_required'
    assert accept(client, old).status_code == accept(client, new).status_code == 409

def test_removal_history_live_pdf_access(db, truck, client):
    row = stage(db); assert accept(client, row).status_code == 200
    event = {'event_type': 'access_removed', 'shop_id': C['shop_id'], 'invoice_id': row.invoice_id, 'event_id': 'event-1', 'effective_updated_at': '2026-09-05T00:00:00Z'}
    stage(db, event); stage(db, event)
    assert row.state == 'access_removed' and db.query(Repair).count() == 1
    assert client.get(f'{BASE}/invoices/{row.id}/pdf', headers=H).status_code == 404
    assert accept(client, row).status_code == 409

def test_bill_to_and_shop_conflicts(db, truck):
    stage(db)
    with pytest.raises(HTTPException): d.stage(db, 1, {**C, 'bill_to_id': 'other'}, item())
    with pytest.raises(HTTPException): d.stage(db, 1, C, item(shop_id='other'))

def test_existing_manual_invoice_held(db, truck, client):
    db.add(Repair(truck_id=truck.id, invoice_number='INV-001', paid_from_reserve=False)); db.commit()
    assert accept(client, stage(db)).status_code == 409
    assert db.query(Repair).count() == 1

def test_stale_accept_and_header_cannot_grant_access(db, truck, client):
    row = stage(db)
    assert accept(client, row, revision='old').status_code == 409
    assert client.get(BASE+'/invoices', headers={'X-Tenant-ID': '2'}).status_code == 404
    assert client.get(BASE+'/invoices').status_code == 400
    assert client.post(f'{BASE}/invoices/{row.id}/accept', headers=H, json={'tenant_id': 2}).status_code == 400

def test_anonymous_no_access(db, client, monkeypatch):
    monkeypatch.delenv('ELIS_FINANCE_LOCAL_TENANTS')
    assert client.get(BASE+'/connections', headers=H).status_code == 401
    assert client.get(BASE+'/invoices', headers=H).status_code == 401

def test_cross_tenant_resource_hidden(db, client):
    db.add(Tenant(id=2, name='Other', business_type='logistics')); db.commit()
    foreign = d.stage(db, 2, C, item()); db.commit()
    assert client.get(f'{BASE}/invoices/{foreign.id}/pdf', headers=H).status_code == 404
    assert accept(client, foreign).status_code == 404
    assert client.get(BASE+'/invoices', headers=H).json()['items'] == []
    assert client.get(BASE+'/invoices?truck_id=999', headers=H).status_code == 404

def test_dry_run_no_persistence(db, truck, client, monkeypatch):
    page_mock(monkeypatch, [item()])
    r = client.post(BASE+'/connections/shop/sync', headers=H)
    assert r.status_code == 200 and r.json()['dry_run']
    assert db.query(Connection).count() == db.query(Invoice).count() == 0

def test_fixed_window_pagination_watermark_and_overlap(db, truck, client, monkeypatch):
    calls = []
    async def page(self, params):
        calls.append(dict(params))
        return {'items': [item(invoice_id='inv-'+str(len(calls)))], 'watermark': params['updated_before'], 'next_cursor': 'opaque' if len(calls) == 1 else None}
    monkeypatch.setattr(d.SourceClient, 'page', page)
    url = BASE+'/connections/shop/sync?dry_run=false'
    assert client.post(url, headers=H).json()['has_more']
    c = db.query(Connection).one()
    assert c.watermark is None and c.cursor == 'opaque'
    assert not client.post(url, headers=H).json()['has_more']
    assert c.watermark and not c.cursor and calls[0]['updated_before'] == calls[1]['updated_before']
    assert calls[1]['cursor'] == 'opaque' and db.query(Invoice).count() == 2
    client.post(url, headers=H)
    assert d.timestamp(calls[2]['updated_since']) == d.timestamp(calls[1]['updated_before']) - timedelta(days=1)

def test_interrupted_page_rolls_back_and_replays(db, truck, client, monkeypatch):
    page_mock(monkeypatch, [item()], 'first')
    url = BASE+'/connections/shop/sync?dry_run=false'
    assert client.post(url, headers=H).status_code == 200
    c = db.query(Connection).one()
    original = d.stage
    def fail_after_stage(db, tenant, config, value):
        row = original(db, tenant, config, value)
        if value['invoice_id'] == 'bad': raise HTTPException(502, 'interrupted')
        return row
    monkeypatch.setattr(d, 'stage', fail_after_stage)
    page_mock(monkeypatch, [item(invoice_id='new'), item(invoice_id='bad')])
    assert client.post(url, headers=H).status_code == 502
    assert db.query(Invoice).count() == 1 and c.cursor == 'first' and c.watermark is None
    monkeypatch.setattr(d, 'stage', original)
    assert client.post(url, headers=H).status_code == 200
    assert db.query(Invoice).count() == 3 and c.cursor is None

def test_key_rotation_restart_and_scope_immutable(db, truck, client, monkeypatch):
    page_mock(monkeypatch, [item()], 'old-key-cursor')
    url = BASE+'/connections/shop/sync?dry_run=false'
    client.post(url, headers=H)
    async def page(self, params):
        assert 'cursor' not in params
        return {'items': [item()], 'watermark': params['updated_before'], 'next_cursor': None}
    monkeypatch.setattr(d.SourceClient, 'page', page)
    monkeypatch.setenv('TEST_DB094_KEY', 'rotated-fixture-token')
    assert client.post(url+'&restart=true', headers=H).status_code == 200 and db.query(Invoice).count() == 1
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS', json.dumps([{**C, 'shop_id': 'other'}]))
    assert client.post(url, headers=H).status_code == 409

@pytest.mark.parametrize('change', [{'watermark': '2026-01-01T00:00:00Z'}, {'items': [item(status='draft')]}, {'next_cursor': 12}, {'items': [item(total_amount='NaN')]}, {'items': [item(event_type='unknown')]}, {'items': [item(effective_updated_at='2999-01-01T00:00:00Z')]}, {'items': [item(shop_id='other')]}])
def test_invalid_source_page_no_progress(db, client, monkeypatch, change):
    async def page(self, params): return {'items': [item()], 'watermark': params['updated_before'], 'next_cursor': None, **change}
    monkeypatch.setattr(d.SourceClient, 'page', page)
    assert client.post(BASE+'/connections/shop/sync?dry_run=false', headers=H).status_code == 502
    assert db.query(Connection).count() == db.query(Invoice).count() == 0

def test_source_api_key_no_redirects(monkeypatch):
    from asyncio import run
    seen = []
    def handler(request):
        seen.append(request); return httpx.Response(302, headers={'location': 'https://other.example'})
    real = httpx.AsyncClient
    monkeypatch.setattr(d.httpx, 'AsyncClient', lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(HTTPException): run(d.SourceClient(C).page({}))
    assert len(seen) == 1 and seen[0].headers['X-API-Key'] == 'fixture-only-token'
    assert seen[0].url.path == '/api/v1/fleet-invoice-exports/invoices'

@pytest.mark.parametrize('status', [401, 404, 500])
def test_source_errors_sanitized(monkeypatch, status):
    from asyncio import run
    real = httpx.AsyncClient
    monkeypatch.setattr(d.httpx, 'AsyncClient', lambda **kw: real(transport=httpx.MockTransport(lambda r: httpx.Response(status, text='private fixture-only-token')), **kw))
    with pytest.raises(HTTPException) as e: run(d.SourceClient(C).page({}))
    assert 'fixture-only-token' not in str(e.value.detail) and 'private' not in str(e.value.detail)

def test_pdf_live_scope_recheck(db, truck, client, monkeypatch):
    row = stage(db); mock = AsyncMock(return_value=b'%PDF-test')
    monkeypatch.setattr(d.SourceClient, 'pdf', mock)
    r = client.get(f'{BASE}/invoices/{row.id}/pdf', headers=H)
    assert r.status_code == 200 and r.content == b'%PDF-test' and r.headers['cache-control'] == 'private, no-store'
    mock.side_effect = HTTPException(404, 'revoked')
    assert client.get(f'{BASE}/invoices/{row.id}/pdf', headers=H).status_code == 404

def test_migration_additive_repeatable(db):
    from sqlalchemy import create_engine, inspect
    from app.database import Base
    from app.migration_runner import _add_dieselbridge_import
    engine = create_engine('sqlite:///:memory:')
    for name in ('tenants', 'trucks', 'repairs'): Base.metadata.tables[name].create(engine)
    _add_dieselbridge_import(engine); _add_dieselbridge_import(engine)
    assert {'dieselbridge_connections', 'dieselbridge_invoices'} <= set(inspect(engine).get_table_names())
