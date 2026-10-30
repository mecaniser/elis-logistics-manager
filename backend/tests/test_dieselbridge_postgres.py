"""Opt-in checks requiring a disposable db094_ PostgreSQL database."""
import asyncio
import os
import threading
import time
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.migration_runner import _add_dieselbridge_import
from app.models.tenant import Tenant
from app.models.truck import Truck
from app.models.repair import Repair
from app.models.finance import FinanceEvent
from app.services import dieselbridge as d

URL = os.getenv('DB094_POSTGRES_TEST_URL')
pytestmark = pytest.mark.skipif(not URL, reason='Disposable PostgreSQL test database not configured')

@pytest.fixture
def postgres(monkeypatch):
    url = make_url(URL)
    if url.get_backend_name() != 'postgresql' or not (url.database or '').startswith('db094_'):
        pytest.fail('Use a disposable db094_ PostgreSQL database')
    engine = create_engine(URL, connect_args={'options': '-c statement_timeout=2000 -c lock_timeout=1000'})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    tenant_id = int(uuid4().hex[:7], 16)
    with sessions() as db:
        db.add(Tenant(id=tenant_id, name=f'DB094 test {tenant_id}', business_type='logistics')); db.flush()
        db.add(Truck(tenant_id=tenant_id, name='Fixture truck', vehicle_type='truck', vin='1M8GDM9AXKP042788')); db.commit()
    monkeypatch.delenv('APP_AUTH_USERNAME', raising=False)
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS', str(tenant_id))
    monkeypatch.setattr(d, 'config', lambda tenant, slug: {'slug': slug, 'tenant_id': tenant, 'shop_id': 'fixture-shop', 'bill_to_id': 'fixture-customer', 'base_url': 'https://fixture.example', 'api_key_env': 'DB094_FIXTURE_KEY'})
    monkeypatch.setenv('DB094_FIXTURE_KEY', 'fixture-only')
    def get_session():
        with sessions() as db: yield db
    app.dependency_overrides[get_db] = get_session
    yield engine, sessions, tenant_id
    app.dependency_overrides.clear(); engine.dispose()


def test_postgres_migration_acceptance_and_replay(postgres):
    engine, sessions, tenant = postgres
    _add_dieselbridge_import(engine); _add_dieselbridge_import(engine)
    assert 'dieselbridge_invoices' in inspect(engine).get_table_names()
    value = {'shop_id': 'fixture-shop', 'invoice_id': str(uuid4()), 'invoice_number': str(uuid4()), 'vin': '1M8GDM9AXKP042788', 'invoice_date': '2026-09-01', 'effective_updated_at': '2026-09-02T00:00:00Z', 'status': 'paid', 'currency': 'USD', 'total_amount': '500.00', 'line_items': {}}
    scope = {'shop_id': 'fixture-shop', 'bill_to_id': 'fixture-customer'}
    with sessions() as db:
        row = d.stage(db, tenant, scope, value); db.commit()
        d.accept(db, tenant, row.id, row.revision, 'Fixture review'); db.commit()
        d.accept(db, tenant, row.id, row.revision, 'Idempotent replay'); db.commit()
        assert db.query(Repair).join(Truck).filter(Truck.tenant_id == tenant).count() == 1
        assert not db.get(Repair, row.repair_id).paid_from_reserve
        assert db.query(FinanceEvent).filter_by(tenant_id=tenant).count() == 0
        d.stage(db, tenant, scope, {**value, 'effective_updated_at': '2026-09-03T00:00:00Z', 'total_amount': '700.00'}); db.commit()
        assert row.state == 'correction_required' and str(db.get(Repair, row.repair_id).cost) == '500.00'


def test_postgres_concurrent_sync_keeps_event_loop_responsive(postgres, monkeypatch):
    engine, sessions, tenant = postgres
    waiting = threading.Event(); calls = []
    async def page(self, params):
        calls.append(threading.current_thread().ident); waiting.set()
        await asyncio.sleep(0.20)
        return {'items': [], 'watermark': params['updated_before'], 'next_cursor': None}
    monkeypatch.setattr(d.SourceClient, 'page', page)
    path = '/db094-test-heartbeat-' + uuid4().hex
    async def heartbeat(): return {'alive': True}
    app.add_api_route(path, heartbeat)
    async def scenario():
        async with httpx.AsyncClient(app=app, base_url='http://testserver') as client:
            endpoint = '/api/v1/accounting/dieselbridge/connections/fixture/sync?dry_run=false'
            headers = {'X-Tenant-ID': str(tenant)}
            first = asyncio.create_task(client.post(endpoint, headers=headers))
            deadline = time.monotonic() + 2
            while not waiting.is_set():
                assert time.monotonic() < deadline
                await asyncio.sleep(0.005)
            second = asyncio.create_task(client.post(endpoint, headers=headers))
            await asyncio.sleep(0.03)
            start = time.monotonic(); probe = await client.get(path)
            assert probe.status_code == 200 and time.monotonic() - start < 0.15
            responses = await asyncio.wait_for(asyncio.gather(first, second), 3)
            assert [r.status_code for r in responses] == [200, 200]
            assert len(calls) == 2 and all(t != threading.current_thread().ident for t in calls)
    try: asyncio.run(scenario())
    finally: app.router.routes[:] = [r for r in app.router.routes if getattr(r, 'path', '') != path]
