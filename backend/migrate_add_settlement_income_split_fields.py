#!/usr/bin/env python3
"""
Migration script to add settlement trailer-income split tracking columns.
Works with both SQLite (local) and PostgreSQL (Railway).
"""
import os
import sys

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import DATABASE_URL, engine


def migrate():
    """Add trailer-income split columns to settlements if they do not exist."""
    columns_to_add = [
        ("trailer_income_split_trailer_id", "INTEGER"),
        ("trailer_income_split_amount", "NUMERIC(10, 2)"),
        ("source_settlement_id", "INTEGER"),
    ]

    if DATABASE_URL.startswith("sqlite"):
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
            cursor.execute("PRAGMA table_info(settlements)")
            existing_columns = {column[1] for column in cursor.fetchall()}

            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    print(f"Adding '{column_name}' column to settlements table...")
                    cursor.execute(f"ALTER TABLE settlements ADD COLUMN {column_name} {column_type}")
                else:
                    print(f"✓ Column '{column_name}' already exists in settlements table. No migration needed.")

            conn.commit()
            print("✓ Settlement income split columns are ready.")
        except Exception as exc:
            print(f"✗ Error adding settlement income split columns: {exc}")
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        from sqlalchemy import text

        with engine.connect() as conn:
            try:
                for column_name, column_type in columns_to_add:
                    result = conn.execute(text("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name='settlements' AND column_name=:column_name
                    """), {"column_name": column_name})

                    if not result.fetchone():
                        print(f"Adding '{column_name}' column to settlements table...")
                        conn.execute(text(f"ALTER TABLE settlements ADD COLUMN {column_name} {column_type}"))
                    else:
                        print(f"✓ Column '{column_name}' already exists in settlements table. No migration needed.")

                conn.commit()
                print("✓ Settlement income split columns are ready.")
            except Exception as exc:
                print(f"✗ Error adding settlement income split columns: {exc}")
                conn.rollback()
                raise

    print("Migration completed successfully!")


if __name__ == "__main__":
    migrate()
