#!/usr/bin/env python3
"""
Migration script to create the vehicle_documents table.
Works with both SQLite (local) and PostgreSQL (Railway).
"""
import os
import sys

from sqlalchemy import text

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import DATABASE_URL, engine


SQLITE_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS vehicle_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    truck_id INTEGER NOT NULL,
    document_type VARCHAR(50) NOT NULL DEFAULT 'other',
    title VARCHAR(255),
    notes VARCHAR(1000),
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100),
    file_size INTEGER,
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_vehicle_document_type CHECK (
        document_type IN ('title', 'inspection', 'registration', 'insurance', 'permit', 'other')
    ),
    FOREIGN KEY(truck_id) REFERENCES trucks(id) ON DELETE CASCADE
)
"""

POSTGRES_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS vehicle_documents (
    id SERIAL PRIMARY KEY,
    truck_id INTEGER NOT NULL REFERENCES trucks(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL DEFAULT 'other',
    title VARCHAR(255),
    notes VARCHAR(1000),
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100),
    file_size INTEGER,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_vehicle_document_type CHECK (
        document_type IN ('title', 'inspection', 'registration', 'insurance', 'permit', 'other')
    )
)
"""

CREATE_INDEX = "CREATE INDEX IF NOT EXISTS ix_vehicle_documents_truck_id ON vehicle_documents (truck_id)"


def migrate():
    """Create vehicle_documents if it does not already exist."""
    if DATABASE_URL.startswith("sqlite"):
        import sqlite3

        db_path = os.path.join(backend_dir, "elisgroup.db")
        if not os.path.exists(db_path):
            print(f"Database file not found at {db_path}")
            print("The table will be created automatically on next app startup.")
            return

        print(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(SQLITE_CREATE_TABLE)
            cursor.execute(CREATE_INDEX)
            conn.commit()
            print("✓ vehicle_documents table is ready.")
        except Exception as exc:
            conn.rollback()
            print(f"✗ Error creating vehicle_documents table: {exc}")
            raise
        finally:
            conn.close()
    else:
        with engine.connect() as conn:
            try:
                conn.execute(text(POSTGRES_CREATE_TABLE))
                conn.execute(text(CREATE_INDEX))
                conn.commit()
                print("✓ vehicle_documents table is ready.")
            except Exception as exc:
                conn.rollback()
                print(f"✗ Error creating vehicle_documents table: {exc}")
                raise

    print("\n✓ Migration completed successfully!")


if __name__ == "__main__":
    migrate()
