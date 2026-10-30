"""Legacy ledger migration preserves data, dependent rows and SQLite schema objects."""
import pytest
import os
from uuid import uuid4
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from app.migration_runner import _add_dieselbridge_financial, _reserve_type_check


def legacy_engine():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as c:
        c.exec_driver_sql('PRAGMA foreign_keys=ON')
        c.exec_driver_sql('CREATE TABLE tenants (id INTEGER PRIMARY KEY)')
        c.exec_driver_sql('CREATE TABLE trucks (id INTEGER PRIMARY KEY, tenant_id INTEGER REFERENCES tenants(id))')
        c.exec_driver_sql('CREATE TABLE repairs (id INTEGER PRIMARY KEY, truck_id INTEGER REFERENCES trucks(id), title TEXT, cost NUMERIC(10,2))')
        c.exec_driver_sql('CREATE TABLE finance_events (id VARCHAR(36) PRIMARY KEY)')
        c.exec_driver_sql('CREATE TABLE finance_evidence (id VARCHAR(36) PRIMARY KEY)')
        c.exec_driver_sql("""CREATE TABLE repair_reserve_ledger (
            id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            truck_id INTEGER NOT NULL REFERENCES trucks(id), entry_date DATE NOT NULL,
            entry_type VARCHAR(20) NOT NULL, amount NUMERIC(10,2) NOT NULL,
            description VARCHAR(255), source_type VARCHAR(20), source_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP, audit_tag TEXT DEFAULT 'legacy',
            CONSTRAINT uq_reserve_source UNIQUE(source_type,source_id,entry_type),
            CONSTRAINT check_reserve_entry_type CHECK(entry_type IN ('deposit','withdrawal','adjustment')),
            CONSTRAINT check_reserve_amount_positive CHECK(amount>0))""")
        c.exec_driver_sql('CREATE INDEX custom_ledger_day ON repair_reserve_ledger(entry_date) WHERE amount>0')
        c.exec_driver_sql('CREATE TABLE legacy_ledger_receipts (id INTEGER PRIMARY KEY, ledger_id INTEGER REFERENCES repair_reserve_ledger(id))')
        c.exec_driver_sql('CREATE TABLE ledger_audit (ledger_id INTEGER)')
        c.exec_driver_sql('CREATE TRIGGER legacy_ledger_insert AFTER INSERT ON repair_reserve_ledger BEGIN INSERT INTO ledger_audit VALUES (NEW.id); END')
        c.exec_driver_sql('CREATE VIEW legacy_ledger_view AS SELECT id,amount,audit_tag FROM repair_reserve_ledger')
        c.exec_driver_sql('INSERT INTO tenants VALUES (1)')
        c.exec_driver_sql('INSERT INTO trucks VALUES (1,1)')
        c.exec_driver_sql("INSERT INTO repairs VALUES(12,1,'Kept repair',3.50)")
        c.exec_driver_sql("INSERT INTO repair_reserve_ledger(id,tenant_id,truck_id,entry_date,entry_type,amount,source_type,source_id,audit_tag) VALUES (1,1,1,'2026-01-02','deposit',10.00,'settlement',7,'keep-deposit'),(2,1,1,'2026-01-03','withdrawal',3.50,'repair',12,'keep-withdrawal')")
        c.exec_driver_sql('INSERT INTO legacy_ledger_receipts VALUES(5,2)')
    return engine


def test_legacy_financial_migration_preserves_every_row_and_schema_object_and_repeats():
    engine=legacy_engine()
    with engine.connect() as c:
        before=c.exec_driver_sql('SELECT * FROM repair_reserve_ledger ORDER BY id').all()
    _add_dieselbridge_financial(engine)
    _add_dieselbridge_financial(engine)
    with engine.begin() as c:
        after=c.exec_driver_sql('SELECT id,tenant_id,truck_id,entry_date,entry_type,amount,description,source_type,source_id,created_at,audit_tag FROM repair_reserve_ledger ORDER BY id').all()
        assert after==before
        assert c.exec_driver_sql('SELECT * FROM legacy_ledger_receipts').all()==[(5,2)]
        assert c.exec_driver_sql('SELECT * FROM ledger_audit').all()==[(1,),(2,)]
        assert c.exec_driver_sql('SELECT audit_tag FROM legacy_ledger_view ORDER BY id').scalars().all()==['keep-deposit','keep-withdrawal']
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar()==1
        assert c.exec_driver_sql('PRAGMA foreign_key_check').all()==[]
        c.exec_driver_sql("INSERT INTO repair_reserve_ledger(id,tenant_id,truck_id,entry_date,entry_type,amount,source_type,source_id,reversal_of_id) VALUES(3,1,1,'2026-02-01','withdrawal_reversal',3.50,'dbn_payment_reverse',8,2)")
        assert c.exec_driver_sql('SELECT * FROM ledger_audit ORDER BY ledger_id').all()==[(1,),(2,),(3,)]
        assert c.exec_driver_sql("SELECT title,cost,archived_at,replaced_by_repair_id,archive_operation_id,archive_reason FROM repairs WHERE id=12").one()==('Kept repair',3.5,None,None,None,None)
    indexes={i['name'] for i in inspect(engine).get_indexes('repair_reserve_ledger')}
    assert 'custom_ledger_day' in indexes
    assert {'dbn_repair_links','dbn_repair_payments','dbn_financial_operations','dieselbridge_financial_inbox'}<=set(inspect(engine).get_table_names())
    for col in inspect(engine).get_columns('repairs'):
        if col['name'] in {'archived_at','replaced_by_repair_id','archive_operation_id','archive_reason'}:
            assert col['nullable']
    with pytest.raises(IntegrityError),engine.begin() as c:
        c.exec_driver_sql("INSERT INTO repair_reserve_ledger(id,tenant_id,truck_id,entry_date,entry_type,amount,reversal_of_id) VALUES(4,1,1,'2026-02-02','withdrawal_reversal',3.50,2)")
    with pytest.raises(IntegrityError),engine.begin() as c:
        c.exec_driver_sql("INSERT INTO repair_reserve_ledger(id,tenant_id,truck_id,entry_date,entry_type,amount) VALUES(5,1,1,'2026-02-02','invalid',3.50)")
    with pytest.raises(IntegrityError),engine.begin() as c:
        c.exec_driver_sql("INSERT INTO repair_reserve_ledger(id,tenant_id,truck_id,entry_date,entry_type,amount,reversal_of_id) VALUES(6,1,1,'2026-02-02','withdrawal_reversal',1.00,999)")


def test_failed_legacy_rebuild_rolls_back_without_losing_original_ledger():
    engine=legacy_engine()
    with engine.connect() as c:
        c.exec_driver_sql('PRAGMA foreign_keys=OFF')
        c.commit()
        c.exec_driver_sql("UPDATE repair_reserve_ledger SET truck_id=999 WHERE id=2")
        c.commit()
        c.exec_driver_sql('PRAGMA foreign_keys=ON')
        c.commit()
    with pytest.raises(RuntimeError,match='foreign key'):
        _add_dieselbridge_financial(engine)
    with engine.connect() as c:
        assert c.exec_driver_sql('SELECT id,truck_id,audit_tag FROM repair_reserve_ledger ORDER BY id').all()==[(1,1,'keep-deposit'),(2,999,'keep-withdrawal')]
        assert c.exec_driver_sql('SELECT * FROM legacy_ledger_receipts').all()==[(5,2)]
        assert c.exec_driver_sql('PRAGMA foreign_keys').scalar()==1
        assert '__db094_reserve_ledger_new' not in inspect(c).get_table_names()
        sql=c.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name='repair_reserve_ledger'").scalar()
        assert 'withdrawal_reversal' not in sql


@pytest.mark.skipif(not os.getenv('DB094_POSTGRES_TEST_URL'),reason='Disposable PostgreSQL database not configured')
@pytest.mark.parametrize('guard_style',['separate_guard','canonical_guard','combined_guard'])
def test_postgres_legacy_financial_migration_preserves_data_and_dependencies(guard_style):
    value=make_url(os.environ['DB094_POSTGRES_TEST_URL'])
    if value.get_backend_name()!='postgresql' or not (value.database or '').startswith('db094_'):
        pytest.fail('Use a disposable db094_ PostgreSQL database')
    schema='db094_migration_'+uuid4().hex
    admin=create_engine(value)
    with admin.begin() as c:
        c.exec_driver_sql('CREATE SCHEMA '+schema)
    engine=create_engine(value,connect_args={'options':'-c search_path='+schema})
    try:
        with engine.begin() as c:
            c.exec_driver_sql('CREATE TABLE tenants(id INTEGER PRIMARY KEY)')
            c.exec_driver_sql('CREATE TABLE trucks(id INTEGER PRIMARY KEY,tenant_id INTEGER REFERENCES tenants(id))')
            c.exec_driver_sql('CREATE TABLE repairs(id INTEGER PRIMARY KEY,truck_id INTEGER REFERENCES trucks(id),title TEXT,cost NUMERIC(10,2))')
            c.exec_driver_sql('CREATE TABLE finance_events(id VARCHAR(36) PRIMARY KEY)')
            c.exec_driver_sql('CREATE TABLE finance_evidence(id VARCHAR(36) PRIMARY KEY)')
            type_name='legacy_types' if guard_style=='canonical_guard' else 'check_reserve_entry_type'
            type_check="entry_type IN ('deposit','withdrawal','adjustment')"
            note_check="entry_type <> 'adjustment' OR audit_tag IS NOT NULL"
            if guard_style=='combined_guard':
                type_check+=' AND ('+note_check+')'
            c.exec_driver_sql(f"CREATE TABLE repair_reserve_ledger(id INTEGER PRIMARY KEY,tenant_id INTEGER REFERENCES tenants(id),truck_id INTEGER REFERENCES trucks(id),entry_date DATE,entry_type VARCHAR(20),amount NUMERIC(10,2),source_type VARCHAR(20),source_id INTEGER,audit_tag TEXT,CONSTRAINT uq_reserve_source UNIQUE(source_type,source_id,entry_type),CONSTRAINT {type_name} CHECK({type_check}),CHECK(amount>0))")
            note_name='check_reserve_entry_type' if guard_style=='canonical_guard' else 'legacy_adjustment_requires_note'
            if guard_style!='combined_guard':
                c.exec_driver_sql(f"ALTER TABLE repair_reserve_ledger ADD CONSTRAINT {note_name} CHECK({note_check})")
            c.exec_driver_sql('CREATE TABLE receipt(id INTEGER PRIMARY KEY,ledger_id INTEGER REFERENCES repair_reserve_ledger(id))')
            c.exec_driver_sql('INSERT INTO tenants VALUES(1)')
            c.exec_driver_sql('INSERT INTO trucks VALUES(1,1)')
            c.exec_driver_sql("INSERT INTO repairs VALUES(12,1,'Unchanged',3.50)")
            c.exec_driver_sql("INSERT INTO repair_reserve_ledger VALUES(2,1,1,'2026-01-02','withdrawal',3.50,'repair',12,'preserved')")
            c.exec_driver_sql('INSERT INTO receipt VALUES(1,2)')
        if guard_style=='combined_guard':
            before=inspect(engine).get_check_constraints('repair_reserve_ledger')
            for _ in range(2):
                with pytest.raises(RuntimeError,match='Unrecognized reserve type allowlist'):
                    _add_dieselbridge_financial(engine)
            assert inspect(engine).get_check_constraints('repair_reserve_ledger')==before
            with engine.connect() as c:
                assert c.exec_driver_sql('SELECT amount,audit_tag FROM repair_reserve_ledger').one()==(3.50,'preserved')
                assert c.exec_driver_sql('SELECT * FROM receipt').all()==[(1,2)]
            return
        _add_dieselbridge_financial(engine);_add_dieselbridge_financial(engine)
        checks={item['name']:item['sqltext'] for item in inspect(engine).get_check_constraints('repair_reserve_ledger')}
        assert note_name in checks
        assert 'audit_tag IS NOT NULL' in checks[note_name]
        with engine.begin() as c:
            assert c.exec_driver_sql('SELECT amount,audit_tag,reversal_of_id FROM repair_reserve_ledger').one()==(3.50,'preserved',None)
            assert c.exec_driver_sql('SELECT * FROM receipt').all()==[(1,2)]
            assert c.exec_driver_sql('SELECT title,archived_at FROM repairs').one()==('Unchanged',None)
            c.exec_driver_sql("INSERT INTO repair_reserve_ledger(id,tenant_id,truck_id,entry_date,entry_type,amount,reversal_of_id) VALUES(3,1,1,'2026-02-01','withdrawal_reversal',3.50,2)")
        with pytest.raises(IntegrityError),engine.begin() as c:
            c.exec_driver_sql("INSERT INTO repair_reserve_ledger(id,tenant_id,truck_id,entry_date,entry_type,amount,reversal_of_id) VALUES(4,1,1,'2026-02-01','withdrawal_reversal',3.50,2)")
        with pytest.raises(IntegrityError),engine.begin() as c:
            c.exec_driver_sql("INSERT INTO repair_reserve_ledger(id,tenant_id,truck_id,entry_date,entry_type,amount,reversal_of_id) VALUES(5,1,1,'2026-02-01','withdrawal_reversal',3.50,999)")
        with pytest.raises(IntegrityError),engine.begin() as c:
            c.exec_driver_sql("INSERT INTO repair_reserve_ledger(id,tenant_id,truck_id,entry_date,entry_type,amount) VALUES(6,1,1,'2026-02-01','adjustment',1.00)")
    finally:
        engine.dispose()
        with admin.begin() as c:
            c.exec_driver_sql('DROP SCHEMA '+schema+' CASCADE')
        admin.dispose()


@pytest.mark.parametrize('expression',[
    "entry_type IN ('deposit','withdrawal','adjustment')",
    "((entry_type)::text = ANY ((ARRAY['deposit'::character varying, 'withdrawal'::character varying, 'adjustment'::character varying])::text[]))",
    "entry_type IN ('adjustment','deposit','withdrawal')",
    '"entry_type"::text = ANY(ARRAY[\'deposit\'::text,\'withdrawal\'::text,\'adjustment\'::text])',
])
def test_type_check_recognizes_only_reflected_standalone_allowlist(expression):
    assert _reserve_type_check(expression,frozenset({'deposit','withdrawal','adjustment'}))


@pytest.mark.parametrize('expression',[
    "entry_type <> 'adjustment' OR audit_tag IS NOT NULL",
    "entry_type IN ('deposit','withdrawal','adjustment') AND audit_tag IS NOT NULL",
    "entry_type IN ('deposit','withdrawal','adjustment') OR audit_tag IS NOT NULL",
    "lower(entry_type) IN ('deposit','withdrawal','adjustment')",
    "entry_type() IN ('deposit','withdrawal','adjustment')",
    "entry_type::custom_type IN ('deposit','withdrawal','adjustment')",
    "other_column IN ('deposit','withdrawal','adjustment')",
    '"ENTRY_TYPE" IN (\'deposit\',\'withdrawal\',\'adjustment\')',
    "entry_type IN ('deposit','withdrawal','adjustment','other')",
])
def test_type_check_does_not_treat_extra_conditions_as_replaceable_allowlist(expression):
    assert not _reserve_type_check(expression,frozenset({'deposit','withdrawal','adjustment'}))
