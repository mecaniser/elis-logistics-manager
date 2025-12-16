"""
Migration script to add business details columns to tenants table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, DATABASE_URL

def migrate():
    """Add business details columns to tenants table"""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("TENANT DETAILS MIGRATION")
        print("=" * 80)

        is_sqlite = DATABASE_URL.startswith("sqlite")
        
        with engine.connect() as connection:
            # Get existing columns
            if is_sqlite:
                result = connection.execute(text("PRAGMA table_info(tenants)"))
                existing_column_names = [row[1] for row in result.fetchall()]
            else:
                # PostgreSQL
                inspector = inspect(engine)
                existing_column_names = [col['name'] for col in inspector.get_columns('tenants')]

            # List of new columns to add
            new_columns = [
                ('ein', 'VARCHAR(20)'),
                ('legal_name', 'VARCHAR(200)'),
                ('address', 'VARCHAR(255)'),
                ('city', 'VARCHAR(100)'),
                ('state', 'VARCHAR(50)'),
                ('zip_code', 'VARCHAR(20)'),
                ('phone', 'VARCHAR(20)'),
                ('email', 'VARCHAR(100)'),
                ('bank_accounts', 'JSON'),
                ('notes', 'VARCHAR(1000)'),
            ]

            for column_name, column_type in new_columns:
                if column_name not in existing_column_names:
                    print(f"Adding column: {column_name} ({column_type})...")
                    try:
                        connection.execute(text(f"ALTER TABLE tenants ADD COLUMN {column_name} {column_type}"))
                        connection.commit()
                        print(f"  ✓ Added {column_name}")
                    except Exception as e:
                        print(f"  ✗ Error adding {column_name}: {e}")
                        connection.rollback()
                else:
                    print(f"  ⏭  Column {column_name} already exists, skipping")

        print("\n" + "=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

