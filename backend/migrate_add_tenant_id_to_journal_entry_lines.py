#!/usr/bin/env python3
"""
Migration: Add tenant_id column to journal_entry_lines table
Populates tenant_id from journal_entry.tenant_id for existing records
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from app.database import DATABASE_URL, SessionLocal
from app.models.journal_entry_line import JournalEntryLine
from app.models.journal_entry import JournalEntry

def migrate():
    """Add tenant_id column to journal_entry_lines and populate from journal_entry"""
    engine = create_engine(DATABASE_URL)
    db = SessionLocal()
    
    try:
        inspector = inspect(engine)
        
        # Check if journal_entry_lines table exists
        if 'journal_entry_lines' not in inspector.get_table_names():
            print("⚠ journal_entry_lines table does not exist. Skipping migration.")
            return
        
        columns = [col['name'] for col in inspector.get_columns('journal_entry_lines')]
        
        # Add tenant_id column if missing
        if 'tenant_id' not in columns:
            print("Adding tenant_id column to journal_entry_lines table...")
            db.execute(text("ALTER TABLE journal_entry_lines ADD COLUMN tenant_id INTEGER"))
            db.commit()
            print("✓ Added tenant_id column to journal_entry_lines")
        else:
            print("✓ tenant_id column already exists in journal_entry_lines")
        
        # Populate tenant_id from journal_entry for existing records
        print("Populating tenant_id from journal_entry.tenant_id...")
        result = db.execute(text("""
            UPDATE journal_entry_lines
            SET tenant_id = (
                SELECT tenant_id 
                FROM journal_entries 
                WHERE journal_entries.id = journal_entry_lines.journal_entry_id
            )
            WHERE tenant_id IS NULL
        """))
        db.commit()
        updated_count = result.rowcount
        print(f"✓ Updated {updated_count} journal_entry_lines records with tenant_id")
        
        # Add NOT NULL constraint if all records have tenant_id
        null_count = db.execute(text("SELECT COUNT(*) FROM journal_entry_lines WHERE tenant_id IS NULL")).scalar()
        if null_count == 0:
            print("Adding NOT NULL constraint to tenant_id...")
            # SQLite doesn't support ALTER COLUMN, so we'll skip this for SQLite
            # For PostgreSQL, we can add the constraint
            db_url_str = str(DATABASE_URL)
            if 'postgresql' in db_url_str or 'postgres' in db_url_str:
                try:
                    db.execute(text("ALTER TABLE journal_entry_lines ALTER COLUMN tenant_id SET NOT NULL"))
                    db.commit()
                    print("✓ Added NOT NULL constraint to tenant_id")
                except Exception as e:
                    print(f"⚠ Could not add NOT NULL constraint: {e}")
            else:
                print("⚠ Skipping NOT NULL constraint (SQLite limitation)")
        else:
            print(f"⚠ {null_count} records still have NULL tenant_id. Cannot add NOT NULL constraint.")
        
        # Add index on tenant_id if it doesn't exist
        indexes = [idx['name'] for idx in inspector.get_indexes('journal_entry_lines')]
        if 'ix_journal_entry_lines_tenant_id' not in indexes:
            print("Adding index on tenant_id...")
            db.execute(text("CREATE INDEX ix_journal_entry_lines_tenant_id ON journal_entry_lines(tenant_id)"))
            db.commit()
            print("✓ Added index on tenant_id")
        else:
            print("✓ Index on tenant_id already exists")
        
        print("\n✓ Migration completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

