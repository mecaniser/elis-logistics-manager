#!/usr/bin/env python3
"""
Migration script to add loan_paid_off_date column to trucks table.
Works with both SQLite (local) and PostgreSQL (Railway).
"""
import os
import sys

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import DATABASE_URL, engine


def migrate():
    """Add loan_paid_off_date column to trucks table if it doesn't exist."""
    is_sqlite = DATABASE_URL.startswith("sqlite")

    if is_sqlite:
        import sqlite3

        db_path = os.path.join(backend_dir, "elisgroup.db")
        if not os.path.exists(db_path):
            print(f"Database file not found at {db_path}")
            print("The database will be created automatically on next app startup.")
            return

        print(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("PRAGMA table_info(trucks)")
            columns = [column[1] for column in cursor.fetchall()]

            if "loan_paid_off_date" not in columns:
                print("Adding 'loan_paid_off_date' column to trucks table...")
                cursor.execute("ALTER TABLE trucks ADD COLUMN loan_paid_off_date DATE")
                conn.commit()
                print("✓ Successfully added 'loan_paid_off_date' column to trucks table.")
            else:
                print("✓ Column 'loan_paid_off_date' already exists in trucks table. No migration needed.")
        except Exception as exc:
            print(f"✗ Error adding column: {exc}")
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        from sqlalchemy import text

        with engine.connect() as conn:
            try:
                result = conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='trucks' AND column_name='loan_paid_off_date'
                """))

                if not result.fetchone():
                    print("Adding 'loan_paid_off_date' column to trucks table...")
                    conn.execute(text("ALTER TABLE trucks ADD COLUMN loan_paid_off_date DATE"))
                    conn.commit()
                    print("✓ Successfully added 'loan_paid_off_date' column to trucks table.")
                else:
                    print("✓ Column 'loan_paid_off_date' already exists in trucks table. No migration needed.")
            except Exception as exc:
                print(f"✗ Error adding column: {exc}")
                conn.rollback()
                raise

    print("Migration completed successfully!")


if __name__ == "__main__":
    migrate()
