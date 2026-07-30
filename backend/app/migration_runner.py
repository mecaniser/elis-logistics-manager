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


# Keep this ordered. New migrations must be additive/idempotent and be added
# here in the same change that introduces their schema or data dependency.
MIGRATIONS: List[Migration] = [
    ("2026_07_29_settlement_cash_adjustments", _add_settlement_cash_adjustments),
    ("2026_07_30_trailer_resale_plan", _add_trailer_resale_plan),
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
