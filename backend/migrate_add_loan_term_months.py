#!/usr/bin/env python3
"""
Migration script to add loan_term_months column to trucks table.
Works with both SQLite (local) and PostgreSQL (Railway).
"""
import sys
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from pathlib import Path

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
            if "loan_term_months" not in columns:
                conn.execute(text("ALTER TABLE trucks ADD COLUMN loan_term_months INTEGER"))
                print("✓ Added 'loan_term_months' column to trucks table")
            else:
                print("✓ Column 'loan_term_months' already exists in trucks table")
    else:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='trucks' AND column_name='loan_term_months'
            """))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE trucks ADD COLUMN loan_term_months INTEGER"))
                conn.commit()
                print("✓ Added 'loan_term_months' column to trucks table")
            else:
                print("✓ Column 'loan_term_months' already exists in trucks table")


if __name__ == "__main__":
    migrate()
    print("\n✓ Migration completed successfully!")
