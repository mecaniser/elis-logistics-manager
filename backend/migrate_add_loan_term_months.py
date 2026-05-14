#!/usr/bin/env python3
"""
Migration script to add loan_term_months column to trucks table.
Works with both SQLite (local) and PostgreSQL (Railway).
"""
import os
import sys

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import DATABASE_URL, Base, engine


def migrate():
    is_sqlite = DATABASE_URL.startswith("sqlite")

    if is_sqlite:
        import sqlite3

        db_path = os.path.join(backend_dir, "elisgroup.db")
        if not os.path.exists(db_path):
            print("Database file not found. Creating new database with all tables...")
            Base.metadata.create_all(bind=engine)
            print("✓ Database created successfully")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("PRAGMA table_info(trucks)")
            columns = [column[1] for column in cursor.fetchall()]
            if "loan_term_months" not in columns:
                cursor.execute("ALTER TABLE trucks ADD COLUMN loan_term_months INTEGER")
                print("✓ Added 'loan_term_months' column to trucks table")
            else:
                print("✓ Column 'loan_term_months' already exists in trucks table")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        from sqlalchemy import text

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
