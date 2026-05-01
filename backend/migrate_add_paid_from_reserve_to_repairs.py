#!/usr/bin/env python3
"""
Migration script to add paid_from_reserve to repairs.
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
    db = SessionLocal()
    try:
        if DATABASE_URL.startswith("sqlite"):
            result = db.execute(text("PRAGMA table_info(repairs)"))
            existing_columns = {row[1] for row in result.fetchall()}
        else:
            result = db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='repairs'
            """))
            existing_columns = {row[0] for row in result.fetchall()}

        if "paid_from_reserve" in existing_columns:
            print("✓ Column 'paid_from_reserve' already exists in repairs table.")
            return 0

        print("Adding 'paid_from_reserve' column to repairs table...")
        db.execute(
            text("ALTER TABLE repairs ADD COLUMN paid_from_reserve BOOLEAN NOT NULL DEFAULT FALSE")
        )
        db.commit()
        print("✓ Repairs paid_from_reserve column is ready.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"✗ Error adding paid_from_reserve column: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    status = migrate()
    sys.exit(0 if status == 0 else 1)
