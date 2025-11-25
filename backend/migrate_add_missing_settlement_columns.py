#!/usr/bin/env python3
"""
Migration script to add missing settlement columns to production database
Adds: custom_expense_validation, reimbursement_details, deduction_details
"""
import os
import sys
from pathlib import Path

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from app.database import SessionLocal, DATABASE_URL

def migrate_add_missing_columns():
    """Add missing columns to settlements table if they don't exist."""
    db = SessionLocal()
    
    try:
        columns_to_add = [
            ('custom_expense_validation', 'JSONB'),
            ('reimbursement_details', 'JSONB'),
            ('deduction_details', 'JSONB')
        ]
        
        # Check which columns exist
        if DATABASE_URL.startswith("sqlite"):
            result = db.execute(text("PRAGMA table_info(settlements)"))
            existing_columns = [row[1] for row in result.fetchall()]
        else:
            # PostgreSQL check
            result = db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='settlements'
            """))
            existing_columns = [row[0] for row in result.fetchall()]
        
        added_count = 0
        for column_name, column_type in columns_to_add:
            if column_name in existing_columns:
                print(f"✓ Column '{column_name}' already exists")
            else:
                print(f"Adding column '{column_name}'...")
                if DATABASE_URL.startswith("sqlite"):
                    db.execute(text(f"ALTER TABLE settlements ADD COLUMN {column_name} TEXT"))
                else:
                    db.execute(text(f"ALTER TABLE settlements ADD COLUMN {column_name} {column_type}"))
                added_count += 1
                print(f"✓ Added column '{column_name}'")
        
        if added_count > 0:
            db.commit()
            print(f"\n✓ Successfully added {added_count} column(s)")
        else:
            print("\n✓ All columns already exist")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error adding columns: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print(f"Database: {'PostgreSQL' if 'postgresql' in DATABASE_URL.lower() else 'SQLite'}")
    print(f"Running migration: add missing settlement columns\n")
    
    success = migrate_add_missing_columns()
    
    if success:
        print("\n✓ Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Migration failed!")
        sys.exit(1)

