"""Notes install independently when the previous financial migration already ran."""
import os
from uuid import uuid4
import pytest
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DatabaseError
from app import migration_runner as migrations
from app.models.dieselbridge_reconciliation import DieselBridgeReconciliationNote as Note


def verify_upgrade(engine,monkeypatch):
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TABLE tenants(id INTEGER PRIMARY KEY)')
        c.exec_driver_sql('INSERT INTO tenants VALUES(1)')
        c.exec_driver_sql('CREATE TABLE schema_migrations(migration_id VARCHAR(120) PRIMARY KEY)')
        c.exec_driver_sql("INSERT INTO schema_migrations VALUES('2026_10_30_dieselbridge_financial')")
    def already_applied(engine):raise AssertionError('Prior financial migration must not rerun')
    monkeypatch.setattr(migrations,'MIGRATIONS',[
        ('2026_10_30_dieselbridge_financial',already_applied),
        ('2026_10_30_dieselbridge_reconciliation_notes',migrations._add_dieselbridge_reconciliation_notes)])
    migrations.run_startup_migrations(engine);migrations.run_startup_migrations(engine)
    assert 'dbn_reconciliation_notes' in inspect(engine).get_table_names()
    with engine.begin() as c:
        c.execute(Note.__table__.insert().values(tenant_id=1,slug='shop',shop_id='shop',customer_id='customer',repair_order_id='ro',note='Retain me',source_references=['ETSINV-1183'],author='owner',created_at='2026-10-30T00:00:00+00:00',key='key',request_digest='a'*64))
    for stmt in ['UPDATE dbn_reconciliation_notes SET note=\'overwrite\'','DELETE FROM dbn_reconciliation_notes']:
        with pytest.raises(DatabaseError),engine.begin() as c:c.exec_driver_sql(stmt)
    migrations.run_startup_migrations(engine)
    with engine.connect() as c:
        assert c.exec_driver_sql('SELECT note FROM dbn_reconciliation_notes').scalar()=='Retain me'


def test_sqlite_prior_financial_install_receives_notes_once(monkeypatch):
    engine=create_engine('sqlite:///:memory:');verify_upgrade(engine,monkeypatch);engine.dispose()


@pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL database not configured')
def test_postgres_prior_financial_install_receives_notes_and_sql_guards(monkeypatch):
    value=make_url(os.environ['DB094_POSTGRES_TEST_URL'])
    if value.get_backend_name()!='postgresql' or not (value.database or '').startswith('db094_'):pytest.fail('Use a disposable db094_ PostgreSQL database')
    admin=create_engine(value);schema='db094_notes_'+uuid4().hex
    with admin.begin() as c:c.exec_driver_sql('CREATE SCHEMA '+schema)
    engine=create_engine(value,connect_args={'options':'-c search_path='+schema})
    try:verify_upgrade(engine,monkeypatch)
    finally:
        engine.dispose()
        with admin.begin() as c:c.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')
        admin.dispose()
