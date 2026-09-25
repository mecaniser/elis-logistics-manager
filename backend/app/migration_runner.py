"""Idempotent application-startup migrations.

Migrations live in the registry below rather than relying on operators to run
ad-hoc scripts. Each migration is recorded only after it succeeds, making a
restart safe. Add every new production-safe migration to ``MIGRATIONS``.
"""
from __future__ import annotations

import logging
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


# Keep this ordered. New migrations must be additive/idempotent and be added
# here in the same change that introduces their schema or data dependency.
MIGRATIONS: List[Migration] = [
    ("2026_07_29_settlement_cash_adjustments", _add_settlement_cash_adjustments),
    ("2026_07_30_trailer_resale_plan", _add_trailer_resale_plan),
    ("2026_09_15_bank_draft_transaction_details", _add_bank_draft_transaction_details),
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
