#!/usr/bin/env python3
"""
Migration script to add settlement trailer-income split tracking columns.
Works with both SQLite (local) and PostgreSQL (Railway).
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from app.database import DATABASE_URL, SessionLocal


def migrate():
    """Add trailer-income split columns to settlements if they do not exist."""
    columns_to_add = [
        ("trailer_income_split_trailer_id", "INTEGER"),
        ("trailer_income_split_amount", "NUMERIC(10, 2)"),
        ("source_settlement_id", "INTEGER"),
    ]
    db = SessionLocal()
    try:
        if DATABASE_URL.startswith("sqlite"):
            result = db.execute(text("PRAGMA table_info(settlements)"))
            existing_columns = {row[1] for row in result.fetchall()}
        else:
            result = db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='settlements'
            """))
            existing_columns = {row[0] for row in result.fetchall()}

        for column_name, column_type in columns_to_add:
            if column_name in existing_columns:
                print(f"✓ Column '{column_name}' already exists in settlements table. No migration needed.")
                continue
            print(f"Adding '{column_name}' column to settlements table...")
            db.execute(text(f"ALTER TABLE settlements ADD COLUMN {column_name} {column_type}"))

        db.commit()
        print("✓ Settlement income split columns are ready.")
        print("Migration completed successfully!")
        return 0
    except Exception as exc:
        print(f"✗ Error adding settlement income split columns: {exc}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success == 0 else 1)
