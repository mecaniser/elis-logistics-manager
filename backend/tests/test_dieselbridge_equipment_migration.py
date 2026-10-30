import os
from uuid import uuid4
import pytest
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DatabaseError
from app import migration_runner as migrations


def verify(engine,monkeypatch):
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TABLE tenants(id INTEGER PRIMARY KEY)')
        c.exec_driver_sql('CREATE TABLE trucks(id INTEGER PRIMARY KEY)')
        c.exec_driver_sql('INSERT INTO tenants VALUES(1)');c.exec_driver_sql('INSERT INTO trucks VALUES(1)')
        c.exec_driver_sql('CREATE TABLE schema_migrations(migration_id VARCHAR(120) PRIMARY KEY)')
        c.exec_driver_sql("INSERT INTO schema_migrations VALUES('2026_10_30_dieselbridge_financial')")
    monkeypatch.setattr(migrations,'MIGRATIONS',[('2026_10_31_dieselbridge_equipment',migrations._add_dieselbridge_equipment)])
    migrations.run_startup_migrations(engine);migrations.run_startup_migrations(engine)
    assert inspect(engine).has_table('dbn_equipment_allocations')
    with engine.begin() as c:
        c.exec_driver_sql("INSERT INTO dbn_equipment_allocations(tenant_id,slug,shop_id,customer_id,repair_order_id,source_vehicle_id,source_vin,asset_id,work_equipment_type,interim_unit_allocation,reason,author,created_at,key,request_digest) VALUES(1,'shop','shop','customer','ro','source','VIN',1,'trailer',1,'Preserved owner decision','owner','2026-10-30','one','digest')")
    migrations.run_startup_migrations(engine)
    with engine.connect() as c:assert c.exec_driver_sql('SELECT count(*) FROM dbn_equipment_allocations').scalar()==1
    for sql in ['DELETE FROM dbn_equipment_allocations',"UPDATE dbn_equipment_allocations SET reason='overwrite'"]:
        with pytest.raises(DatabaseError),engine.begin() as c:c.execute(text(sql))


def test_prior_install_adds_equipment_without_rewriting_data(monkeypatch):
    engine=create_engine('sqlite:///:memory:')
    try:verify(engine,monkeypatch)
    finally:engine.dispose()


@pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL test database not configured')
def test_postgres_upgrade_and_audit_guards(monkeypatch):
    value=make_url(os.environ['DB094_POSTGRES_TEST_URL'])
    assert (value.database or '').startswith('db094_')
    admin=create_engine(value);schema='db094_equipment_'+uuid4().hex
    with admin.begin() as c:c.exec_driver_sql('CREATE SCHEMA '+schema)
    engine=create_engine(value,connect_args={'options':'-c search_path='+schema})
    try:verify(engine,monkeypatch)
    finally:
        engine.dispose()
        with admin.begin() as c:c.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')
        admin.dispose()
