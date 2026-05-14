#!/usr/bin/env python3
"""
Migration script to add trailer_depreciation_reserve_amount column to trucks table.
Works with both SQLite (local) and PostgreSQL (Railway).
"""
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.database import DATABASE_URL, Base, engine


def migrate():
    is_sqlite = DATABASE_URL.startswith("sqlite")

    if is_sqlite:
        with engine.begin() as conn:
            try:
                rows = conn.execute(text("PRAGMA table_info(trucks)")).fetchall()
            except OperationalError:
                rows = []

            if not rows:
                print("Trucks table not found. Creating new database with all tables...")
                Base.metadata.create_all(bind=engine)
                print("✓ Database created successfully")
                return

            columns = [row[1] for row in rows]
            if "trailer_depreciation_reserve_amount" not in columns:
                conn.execute(text("ALTER TABLE trucks ADD COLUMN trailer_depreciation_reserve_amount NUMERIC(10, 2)"))
                conn.execute(text("""
                    UPDATE trucks
                    SET trailer_depreciation_reserve_amount = 160
                    WHERE vehicle_type = 'trailer'
                      AND trailer_depreciation_reserve_amount IS NULL
                """))
                print("✓ Added 'trailer_depreciation_reserve_amount' column to trucks table")
            else:
                print("✓ Column 'trailer_depreciation_reserve_amount' already exists in trucks table")
    else:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='trucks'
                  AND column_name='trailer_depreciation_reserve_amount'
            """))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE trucks ADD COLUMN trailer_depreciation_reserve_amount NUMERIC(10, 2)"))
                conn.execute(text("""
                    UPDATE trucks
                    SET trailer_depreciation_reserve_amount = 160
                    WHERE vehicle_type = 'trailer'
                      AND trailer_depreciation_reserve_amount IS NULL
                """))
                conn.commit()
                print("✓ Added 'trailer_depreciation_reserve_amount' column to trucks table")
            else:
                print("✓ Column 'trailer_depreciation_reserve_amount' already exists in trucks table")


if __name__ == "__main__":
    migrate()
    print("\n✓ Migration completed successfully!")
