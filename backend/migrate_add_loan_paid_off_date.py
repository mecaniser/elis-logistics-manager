#!/usr/bin/env python3
"""
Migration script to add loan_paid_off_date column to trucks table.
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
    """Add loan_paid_off_date column to trucks table if it doesn't exist."""
    db = SessionLocal()
    try:
        if DATABASE_URL.startswith("sqlite"):
            result = db.execute(text("PRAGMA table_info(trucks)"))
            columns = {row[1] for row in result.fetchall()}
        else:
            result = db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='trucks'
            """))
            columns = {row[0] for row in result.fetchall()}

        if "loan_paid_off_date" in columns:
            print("✓ Column 'loan_paid_off_date' already exists in trucks table. No migration needed.")
            return 0

        print("Adding 'loan_paid_off_date' column to trucks table...")
        db.execute(text("ALTER TABLE trucks ADD COLUMN loan_paid_off_date DATE"))
        db.commit()
        print("✓ Successfully added 'loan_paid_off_date' column to trucks table.")
        print("Migration completed successfully!")
        return 0
    except Exception as exc:
        print(f"✗ Error adding column: {exc}")
        db.rollback()
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success == 0 else 1)
