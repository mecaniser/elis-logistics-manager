import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from app.database import Base
from app.migration_runner import run_startup_migrations


def test_existing_finance_tables_receive_guards_and_migration_is_repeatable():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text('DROP TRIGGER finance_reports_no_update'))
        c.execute(text("INSERT INTO finance_reports (id,tenant_id,result) VALUES ('probe',1,'{}')"))
    run_startup_migrations(engine)
    run_startup_migrations(engine)
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM schema_migrations WHERE migration_id='2026_09_24_reconciled_finance'")).scalar() == 1
        assert c.execute(text("SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'finance_%'")).scalar() == 10
    for statement in ["UPDATE finance_reports SET result='{}' WHERE id='probe'", "DELETE FROM finance_reports WHERE id='probe'"]:
        with pytest.raises(DatabaseError, match='immutable'):
            with engine.begin() as c:
                c.execute(text(statement))
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM finance_reports WHERE id='probe'")).scalar() == 1
    engine.dispose()
