#!/usr/bin/env python3
"""
Migration script to add overview_amounts to settlements.
Stores display-only derived values such as 77 Cargo dispatch-fee gap.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from app.database import SessionLocal, DATABASE_URL


def migrate():
    """Add overview_amounts column to settlements if it does not exist."""
    db = SessionLocal()
    try:
        if DATABASE_URL.startswith("sqlite"):
            result = db.execute(text("PRAGMA table_info(settlements)"))
            existing_columns = [row[1] for row in result.fetchall()]
        else:
            result = db.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='settlements'
            """))
            existing_columns = [row[0] for row in result.fetchall()]

        if "overview_amounts" in existing_columns:
            print("✓ Column 'overview_amounts' already exists")
            return True

        print("Adding column 'overview_amounts'...")
        if DATABASE_URL.startswith("sqlite"):
            db.execute(text("ALTER TABLE settlements ADD COLUMN overview_amounts TEXT"))
        else:
            db.execute(text("ALTER TABLE settlements ADD COLUMN overview_amounts JSONB"))
        db.commit()
        print("✓ Added column 'overview_amounts'")
        return True
    except Exception as e:
        db.rollback()
        print(f"✗ Error adding column: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
