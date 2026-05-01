#!/usr/bin/env python3
"""
Migration script to add repair reserve fields to trucks and settlements.
Works with both SQLite (local) and PostgreSQL (Railway).
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from app.database import SessionLocal, DATABASE_URL


def migrate():
    """Add default repair reserve columns to trucks and settlements if missing."""
    db = SessionLocal()

    try:
        columns_to_add = {
            "trucks": [
                ("default_repair_reserve_amount", "NUMERIC(10, 2)"),
            ],
            "settlements": [
                ("repair_reserve_amount", "NUMERIC(10, 2)"),
            ],
        }

        for table_name, table_columns in columns_to_add.items():
            if DATABASE_URL.startswith("sqlite"):
                result = db.execute(text(f"PRAGMA table_info({table_name})"))
                existing_columns = [row[1] for row in result.fetchall()]
            else:
                result = db.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name=:table_name
                """), {"table_name": table_name})
                existing_columns = [row[0] for row in result.fetchall()]

            for column_name, column_type in table_columns:
                if column_name in existing_columns:
                    print(f"✓ Column '{column_name}' already exists in {table_name} table.")
                    continue

                print(f"Adding '{column_name}' column to {table_name} table...")
                db.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))

        db.commit()
        print("✓ Repair reserve columns are ready.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"✗ Error adding repair reserve columns: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    status = migrate()
    if status == 0:
        print("Migration completed successfully!")
        sys.exit(0)
    print("Migration failed!")
    sys.exit(1)
