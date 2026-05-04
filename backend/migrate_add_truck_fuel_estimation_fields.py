#!/usr/bin/env python3
"""
Migration script to add truck fuel-estimation settings.
Works with both SQLite (local) and PostgreSQL (Railway).
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text

from app.database import DATABASE_URL, SessionLocal


def migrate():
    """Add truck MPG and per-gallon fuel-discount columns if they do not exist."""
    db = SessionLocal()

    try:
        columns_to_add = [
            ("estimated_mpg", "NUMERIC(6, 2)"),
            ("fuel_card_discount_per_gallon", "NUMERIC(6, 3)"),
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

        db.execute(text("""
            UPDATE trucks
            SET estimated_mpg = 6.50
            WHERE vehicle_type = 'truck'
              AND estimated_mpg IS NULL
        """))
        db.execute(text("""
            UPDATE trucks
            SET fuel_card_discount_per_gallon = 0
            WHERE vehicle_type = 'truck'
              AND fuel_card_discount_per_gallon IS NULL
        """))

        db.commit()
        print("✓ Truck fuel-estimation columns are ready.")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"✗ Error adding truck fuel-estimation columns: {exc}")
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
