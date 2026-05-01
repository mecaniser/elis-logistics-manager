#!/usr/bin/env python3
"""
Migration script to add default trailer split settings to trucks.
Works with both SQLite (local) and PostgreSQL (Railway).
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from app.database import SessionLocal, DATABASE_URL


def migrate():
    """Add default trailer split columns to trucks if they do not exist."""
    db = SessionLocal()

    try:
        columns_to_add = [
            ("default_trailer_id", "INTEGER"),
            ("default_trailer_income_split_amount", "NUMERIC(10, 2)"),
        ]

        if DATABASE_URL.startswith("sqlite"):
            result = db.execute(text("PRAGMA table_info(trucks)"))
            existing_columns = [row[1] for row in result.fetchall()]
        else:
            result = db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='trucks'
            """))
            existing_columns = [row[0] for row in result.fetchall()]

        for column_name, column_type in columns_to_add:
            if column_name in existing_columns:
                print(f"✓ Column '{column_name}' already exists in trucks table.")
                continue

            print(f"Adding '{column_name}' column to trucks table...")
            db.execute(text(f"ALTER TABLE trucks ADD COLUMN {column_name} {column_type}"))

        db.commit()
        print("✓ Default trailer split columns are ready.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"✗ Error adding default trailer split columns: {exc}")
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
