"""Idempotent application-startup migrations.

Migrations live in the registry below rather than relying on operators to run
ad-hoc scripts. Each migration is recorded only after it succeeds, making a
restart safe. Add every new production-safe migration to ``MIGRATIONS``.
"""
from __future__ import annotations

import logging
import re
from typing import Callable, List, Tuple

from sqlalchemy import Engine, inspect, text

logger = logging.getLogger(__name__)

Migration = Tuple[str, Callable[[Engine], None]]


def _add_settlement_cash_adjustments(engine: Engine) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("settlements")}
    statements = []
    if "cash_settlement_amount" not in columns:
        statements.append("ALTER TABLE settlements ADD COLUMN cash_settlement_amount NUMERIC(10, 2)")
    if "cash_adjustments" not in columns:
        statements.append(
            "ALTER TABLE settlements ADD COLUMN cash_adjustments "
            + ("TEXT" if engine.dialect.name == "sqlite" else "JSON")
        )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _add_trailer_resale_plan(engine: Engine) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("trucks")}
    statements = []
    if "expected_resale_value" not in columns:
        statements.append("ALTER TABLE trucks ADD COLUMN expected_resale_value NUMERIC(10, 2)")
    if "planned_service_weeks" not in columns:
        statements.append("ALTER TABLE trucks ADD COLUMN planned_service_weeks INTEGER")
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _add_bank_draft_transaction_details(engine: Engine) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("bank_transfer_drafts")}
    statements = []
    if "bank_state" not in columns:
        statements.append("ALTER TABLE bank_transfer_drafts ADD COLUMN bank_state VARCHAR(12)")
    if "bank_effective_date" not in columns:
        statements.append("ALTER TABLE bank_transfer_drafts ADD COLUMN bank_effective_date DATE")
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _add_bank_draft_reserve_override(engine: Engine) -> None:
    columns = {column['name'] for column in inspect(engine).get_columns('bank_transfer_drafts')}
    if 'reserve_override' not in columns:
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE bank_transfer_drafts ADD COLUMN reserve_override BOOLEAN NOT NULL DEFAULT FALSE'))


def _add_reconciled_finance(engine: Engine) -> None:
    """Install additive tables and protect existing tables restored without triggers."""
    from app.models.finance import FinanceEvent, FinanceEvidence, FinancePosting, FinanceLine, FinanceReport
    models = (FinanceEvent, FinanceEvidence, FinancePosting, FinanceLine, FinanceReport)
    with engine.begin() as connection:
        for model in models:
            model.__table__.create(connection, checkfirst=True)
        for model in models:
            table = model.__tablename__
            if engine.dialect.name == 'postgresql':
                connection.execute(text(
                    f"CREATE OR REPLACE FUNCTION {table}_immutable() RETURNS trigger AS $$ "
                    "BEGIN RAISE EXCEPTION 'Accounting history is immutable'; END; $$ LANGUAGE plpgsql"
                ))
                connection.execute(text(f'DROP TRIGGER IF EXISTS {table}_immutable ON {table}'))
                connection.execute(text(
                    f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} '
                    f'FOR EACH ROW EXECUTE FUNCTION {table}_immutable()'
                ))
            elif engine.dialect.name == 'sqlite':
                for operation in ('UPDATE', 'DELETE'):
                    connection.execute(text(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} "
                        f"BEFORE {operation} ON {table} BEGIN "
                        "SELECT RAISE(ABORT, 'Accounting history is immutable'); END"
                    ))
            else:
                raise RuntimeError('Reconciled finance requires PostgreSQL or SQLite history guards.')


def _add_auth_account(engine: Engine) -> None:
    from app.models.auth_account import AuthAccount
    AuthAccount.__table__.create(engine, checkfirst=True)


def _add_auth_login_throttle(engine: Engine) -> None:
    columns = {column['name'] for column in inspect(engine).get_columns('auth_account')}
    with engine.begin() as connection:
        if 'failed_login_count' not in columns:
            connection.execute(text('ALTER TABLE auth_account ADD COLUMN failed_login_count INTEGER NOT NULL DEFAULT 0'))
        if 'login_retry_after' not in columns:
            connection.execute(text('ALTER TABLE auth_account ADD COLUMN login_retry_after BIGINT'))


def _add_auth_recovery_email(engine: Engine) -> None:
    columns = {column['name'] for column in inspect(engine).get_columns('auth_account')}
    statements = {
        'recovery_email': 'VARCHAR(254)',
        'pending_recovery_email': 'VARCHAR(254)',
        'pending_recovery_token_hash': 'VARCHAR(64)',
        'pending_recovery_expires_at': 'BIGINT',
        'recovery_email_requested_at': 'BIGINT',
    }
    with engine.begin() as connection:
        for name, sql_type in statements.items():
            if name not in columns:
                connection.execute(text(f'ALTER TABLE auth_account ADD COLUMN {name} {sql_type}'))


def _add_dieselbridge_import(engine: Engine) -> None:
    from app.models.dieselbridge import DieselBridgeConnection, DieselBridgeInvoice
    with engine.begin() as connection:
        for model in (DieselBridgeConnection, DieselBridgeInvoice):
            model.__table__.create(connection, checkfirst=True)


def _add_dieselbridge_repair_history(engine: Engine) -> None:
    from app.models.dieselbridge import DieselBridgeRepairHistory, DieselBridgeHistorySync
    with engine.begin() as connection:
        for model in (DieselBridgeRepairHistory, DieselBridgeHistorySync):
            model.__table__.create(connection, checkfirst=True)


def _sqlite_expand_reserve_types(engine: Engine) -> None:
    """Rebuild only the old check, retaining unknown columns and schema objects.

    SQLite cannot alter a CHECK constraint. Keep the original CREATE statement
    and explicitly copy its columns instead of recreating from the current ORM,
    which could discard a restored database's extra legacy fields. Foreign keys
    are disabled only on this connection during one rollback-capable transaction.
    """
    raw = engine.raw_connection()
    cursor = raw.cursor()
    foreign_keys = cursor.execute('PRAGMA foreign_keys').fetchone()[0]
    legacy_alter = cursor.execute('PRAGMA legacy_alter_table').fetchone()[0]
    try:
        cursor.execute('PRAGMA foreign_keys=OFF')
        cursor.execute('PRAGMA legacy_alter_table=ON')
        cursor.execute('BEGIN IMMEDIATE')
        sql = cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='repair_reserve_ledger'").fetchone()[0]
        if 'withdrawal_reversal' in sql:
            raw.rollback()
            return
        if cursor.execute("SELECT 1 FROM sqlite_master WHERE name='__db094_reserve_ledger_new'").fetchone():
            raise RuntimeError('Unexpected reserve migration table; inspect before retrying.')
        new_sql, changed = re.subn(
            r"(entry_type\s+IN\s*\(\s*'deposit'\s*,\s*'withdrawal'\s*,\s*'adjustment')(\s*\))",
            r"\1, 'withdrawal_reversal'\2", sql, flags=re.IGNORECASE,
        )
        if changed != 1:
            raise RuntimeError('Unrecognized reserve check; original ledger preserved.')
        new_sql, renamed = re.subn(
            r'^CREATE TABLE(?: IF NOT EXISTS)?\s+(?:"repair_reserve_ledger"|`repair_reserve_ledger`|\[repair_reserve_ledger\]|repair_reserve_ledger)',
            'CREATE TABLE "__db094_reserve_ledger_new"', new_sql, count=1, flags=re.IGNORECASE,
        )
        if renamed != 1:
            raise RuntimeError('Unrecognized reserve table definition; original ledger preserved.')
        objects = cursor.execute("SELECT sql FROM sqlite_master WHERE tbl_name='repair_reserve_ledger' AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY type,name").fetchall()
        names = [r[1] for r in cursor.execute('PRAGMA table_info(repair_reserve_ledger)').fetchall()]
        columns = ','.join('"'+name.replace('"','""')+'"' for name in names)
        cursor.execute(new_sql)
        cursor.execute(f'INSERT INTO "__db094_reserve_ledger_new" ({columns}) SELECT {columns} FROM repair_reserve_ledger')
        cursor.execute('DROP TABLE repair_reserve_ledger')
        cursor.execute('ALTER TABLE "__db094_reserve_ledger_new" RENAME TO repair_reserve_ledger')
        for (statement,) in objects:
            cursor.execute(statement)
        if cursor.execute('PRAGMA foreign_key_check').fetchall():
            raise RuntimeError('Reserve migration found foreign key violations; original ledger preserved.')
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        cursor.execute(f'PRAGMA legacy_alter_table={int(legacy_alter)}')
        cursor.execute(f'PRAGMA foreign_keys={int(foreign_keys)}')
        cursor.close()
        raw.close()


def _reserve_type_check(sql: str, values: frozenset[str]) -> bool:
    """Recognize only the standalone type allowlist, including PG reflection.

    PostgreSQL rewrites IN into = ANY(ARRAY[...]) and adds casts/parentheses.
    No constraint name or mention of entry_type makes an arbitrary condition
    safe to replace. Any extra column, AND/OR, operator or function fails this
    exact grammar check and is retained for explicit review.
    """
    literal = r"'(?:''|[^'])*'"
    quoted = re.findall(literal, sql)
    if len(quoted) != len(values) or {s[1:-1].replace("''", "'") for s in quoted} != values:
        return False
    shape = re.sub(literal, '@', sql)
    if any(identifier != 'entry_type' for identifier in re.findall(r'"([^"]*)"', shape)):
        return False  # Quoted identifiers are case-sensitive in PostgreSQL.
    shape = re.sub(r'::\s*(?:character\s+varying|varchar|text)(?:\s*\(\s*[0-9]+\s*\))?(?:\s*\[\s*\])?', '', shape, flags=re.IGNORECASE)
    if re.search(r'(?:\bentry_type|"entry_type")\s*\(', shape, flags=re.IGNORECASE):
        return False  # A function named entry_type is not the column allowlist.
    shape = re.sub(r'[\s()]', '', shape).lower().replace('"entry_type"', 'entry_type')
    members = ','.join('@' for _ in values)
    return shape in {f'entry_typein{members}', f'entry_type=anyarray[{members}]'}


def _postgres_expand_reserve_types(engine: Engine) -> None:
    old_types = frozenset({'deposit', 'withdrawal', 'adjustment'})
    new_types = old_types | {'withdrawal_reversal'}
    checks = inspect(engine).get_check_constraints('repair_reserve_ledger')
    old_checks = [c for c in checks if _reserve_type_check(c['sqltext'], old_types)]
    new_checks = [c for c in checks if _reserve_type_check(c['sqltext'], new_types)]
    # A combined old allowlist plus an extra guard cannot be safely rewritten;
    # preserving it would also continue rejecting the new reversal type.
    for check in checks:
        sql = check['sqltext']
        literals = {s[1:-1].replace("''", "'") for s in re.findall(r"'(?:''|[^'])*'", sql)}
        if (old_types <= literals and re.search(r'\bentry_type\b', sql, re.IGNORECASE)
                and re.search(r'\b(?:IN|ANY|ARRAY)\b', sql, re.IGNORECASE)
                and check not in old_checks and check not in new_checks):
            raise RuntimeError('Unrecognized reserve type allowlist; original constraints preserved.')
    if not old_checks and not new_checks:
        raise RuntimeError('Unrecognized reserve type allowlist; original constraints preserved.')
    with engine.begin() as connection:
        for check in old_checks:
            name = engine.dialect.identifier_preparer.quote(check['name'])
            connection.execute(text(f'ALTER TABLE repair_reserve_ledger DROP CONSTRAINT {name}'))
        if not new_checks:
            # A custom guard may itself have the historical canonical name.
            remaining = {c['name'] for c in checks if c not in old_checks}
            name = 'check_reserve_entry_type'
            if name in remaining:
                name = 'check_db094_reserve_entry_type'
                index = 1
                while name in remaining:
                    name = f'check_db094_reserve_entry_type_{index}'
                    index += 1
            quoted = engine.dialect.identifier_preparer.quote(name)
            connection.execute(text(f"ALTER TABLE repair_reserve_ledger ADD CONSTRAINT {quoted} CHECK(entry_type IN ('deposit','withdrawal','adjustment','withdrawal_reversal'))"))


def _add_dieselbridge_financial(engine: Engine) -> None:
    """Upgrade existing repair/ledger schemas before installing financial links."""
    from app.models.dieselbridge import DieselBridgeRepairLink, DieselBridgeRepairPayment, DieselBridgeFinancialOperation
    from app.models.dieselbridge_events import DieselBridgeFinancialInbox
    repair_columns = {c['name'] for c in inspect(engine).get_columns('repairs')}
    archive_columns = {
        'archived_at': 'TIMESTAMP WITH TIME ZONE' if engine.dialect.name == 'postgresql' else 'DATETIME',
        'replaced_by_repair_id': 'INTEGER REFERENCES repairs(id)',
        'archive_operation_id': 'VARCHAR(80)',
        'archive_reason': 'VARCHAR(500)',
    }
    ledger_columns = {c['name'] for c in inspect(engine).get_columns('repair_reserve_ledger')}
    with engine.begin() as connection:
        for name, kind in archive_columns.items():
            if name not in repair_columns:
                connection.execute(text(f'ALTER TABLE repairs ADD COLUMN {name} {kind}'))
        if 'reversal_of_id' not in ledger_columns:
            connection.execute(text('ALTER TABLE repair_reserve_ledger ADD COLUMN reversal_of_id INTEGER REFERENCES repair_reserve_ledger(id)'))
    if engine.dialect.name == 'sqlite':
        _sqlite_expand_reserve_types(engine)
    elif engine.dialect.name == 'postgresql':
        _postgres_expand_reserve_types(engine)
    else:
        raise RuntimeError('DieselBridge financial migration requires PostgreSQL or SQLite.')
    constraints = inspect(engine).get_unique_constraints('repair_reserve_ledger')
    indexes = inspect(engine).get_indexes('repair_reserve_ledger')
    reversal_unique = any(c.get('column_names') == ['reversal_of_id'] for c in constraints)
    reversal_unique |= any(c.get('unique') and c.get('column_names') == ['reversal_of_id'] for c in indexes)
    with engine.begin() as connection:
        if not reversal_unique:
            connection.execute(text('CREATE UNIQUE INDEX ux_repair_reserve_reversal_of_id ON repair_reserve_ledger(reversal_of_id)'))
        for model in (DieselBridgeRepairLink, DieselBridgeRepairPayment, DieselBridgeFinancialOperation, DieselBridgeFinancialInbox):
            model.__table__.create(connection, checkfirst=True)


# Keep this ordered. New migrations must be additive/idempotent and be added
# here in the same change that introduces their schema or data dependency.
def _add_investment_plans(engine: Engine) -> None:
    if 'investment_plans' not in {c['name'] for c in inspect(engine).get_columns('trucks')}:
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE trucks ADD COLUMN investment_plans JSON'))


def _add_dieselbridge_reconciliation_notes(engine: Engine) -> None:
    from app.models.dieselbridge_reconciliation import DieselBridgeReconciliationNote
    with engine.begin() as connection:
        DieselBridgeReconciliationNote.__table__.create(connection, checkfirst=True)


def _add_dieselbridge_settlement_observations(engine: Engine) -> None:
    changes={'dbn_repair_links':{'source_settlement_payload':'JSON','source_payment_review_reasons':'JSON'},'dbn_repair_payments':{'source_attempt_id':'VARCHAR(80)','source_attempt_revision':'VARCHAR(64)','source_shop_id':'VARCHAR(80)'}}
    with engine.begin() as connection:
        for table,columns in changes.items():
            if table not in inspect(connection).get_table_names():continue
            existing={c['name'] for c in inspect(connection).get_columns(table)}
            for name,kind in columns.items():
                if name not in existing:connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {kind}'))
        if 'dbn_repair_payments' in inspect(connection).get_table_names():
            connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_dbn_active_source_payment ON dbn_repair_payments(tenant_id,source_shop_id,source_attempt_id) WHERE source_attempt_id IS NOT NULL AND reversal_event_id IS NULL'))


MIGRATIONS: List[Migration] = [
    ("2026_10_30_dieselbridge_reconciliation_notes", _add_dieselbridge_reconciliation_notes),
    ("2026_10_30_dieselbridge_financial", _add_dieselbridge_financial),
    ("2026_10_30_dieselbridge_settlement_observations", _add_dieselbridge_settlement_observations),
    ("2026_10_30_dieselbridge_repair_history", _add_dieselbridge_repair_history),
    ("2026_10_30_dieselbridge_import", _add_dieselbridge_import),
    ('2026_09_28_investment_plans', _add_investment_plans),
    ("2026_07_29_settlement_cash_adjustments", _add_settlement_cash_adjustments),
    ("2026_07_30_trailer_resale_plan", _add_trailer_resale_plan),
    ("2026_09_15_bank_draft_transaction_details", _add_bank_draft_transaction_details),
    ("2026_10_19_bank_draft_reserve_override", _add_bank_draft_reserve_override),
    ("2026_09_24_reconciled_finance", _add_reconciled_finance),


    ("2026_09_24_auth_account", _add_auth_account),
    ("2026_09_24_auth_login_throttle", _add_auth_login_throttle),
    ("2026_09_24_auth_recovery_email", _add_auth_recovery_email),
]


def run_startup_migrations(engine: Engine) -> None:
    """Apply each registered migration once and persist its completion."""
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_id VARCHAR(120) PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

    for migration_id, apply in MIGRATIONS:
        with engine.connect() as connection:
            already_applied = connection.execute(
                text("SELECT 1 FROM schema_migrations WHERE migration_id = :migration_id"),
                {"migration_id": migration_id},
            ).first()
        if already_applied:
            continue

        logger.info("Applying database migration %s", migration_id)
        apply(engine)
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO schema_migrations (migration_id) VALUES (:migration_id)"),
                {"migration_id": migration_id},
            )
        logger.info("Applied database migration %s", migration_id)
