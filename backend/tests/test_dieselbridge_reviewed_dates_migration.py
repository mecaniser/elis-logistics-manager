"""Upgrade existing immutable notes without silently promoting reference dates."""
import os
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DatabaseError
from app import migration_runner as migrations


def verify_upgrade(engine):
    with engine.begin() as c:
        c.exec_driver_sql('CREATE TABLE tenants(id INTEGER PRIMARY KEY)')
        c.exec_driver_sql('INSERT INTO tenants VALUES(1)')
        c.exec_driver_sql("CREATE TABLE dbn_reconciliation_notes(id INTEGER PRIMARY KEY, note TEXT, confirmed_service_date DATE)")
        c.exec_driver_sql("INSERT INTO dbn_reconciliation_notes VALUES(1,'Historical reference only','2026-07-13')")
        if engine.dialect.name=='sqlite':
            c.exec_driver_sql("CREATE TRIGGER old_note_guard BEFORE UPDATE ON dbn_reconciliation_notes BEGIN SELECT RAISE(ABORT,'immutable'); END")
        else:
            c.exec_driver_sql("CREATE FUNCTION old_note_guard() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'immutable'; END; $$ LANGUAGE plpgsql")
            c.exec_driver_sql('CREATE TRIGGER old_note_guard BEFORE UPDATE ON dbn_reconciliation_notes FOR EACH ROW EXECUTE FUNCTION old_note_guard()')
    migrations._add_dieselbridge_reviewed_dates(engine);migrations._add_dieselbridge_reviewed_dates(engine)
    with engine.connect() as c:
        row=c.execute(text('SELECT note,confirmed_service_date,date_treatment,source_revision FROM dbn_reconciliation_notes')).one()
        assert row[0]=='Historical reference only' and str(row[1])=='2026-07-13' and row[2]=='note_only' and row[3] is None
    with pytest.raises(DatabaseError),engine.begin() as c:
        c.exec_driver_sql("UPDATE dbn_reconciliation_notes SET date_treatment='confirmed_service_date'")


def test_sqlite_upgrade_is_replay_safe_and_keeps_old_notes_informational():
    engine=create_engine('sqlite:///:memory:')
    try:verify_upgrade(engine)
    finally:engine.dispose()


@pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL database not configured')
def test_postgres_upgrade_keeps_immutable_history():
    url=make_url(os.environ['DB094_POSTGRES_TEST_URL'])
    assert url.get_backend_name()=='postgresql' and (url.database or '').startswith('db094_')
    admin=create_engine(url);schema='db094_dates_'+uuid4().hex
    with admin.begin() as c:c.exec_driver_sql('CREATE SCHEMA '+schema)
    engine=create_engine(url,connect_args={'options':'-c search_path='+schema})
    try:verify_upgrade(engine)
    finally:
        engine.dispose()
        with admin.begin() as c:c.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')
        admin.dispose()
