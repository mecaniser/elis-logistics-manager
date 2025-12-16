#!/usr/bin/env python3
"""
Migration script to add duplicate_block_ids_warning column to settlements table
Works with both SQLite (local) and PostgreSQL (Railway)
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

def migrate():
    """Add duplicate_block_ids_warning column to settlements table if it doesn't exist."""
    db = SessionLocal()
    
    try:
        # Check if column already exists
        if DATABASE_URL.startswith("sqlite"):
            # SQLite check
            result = db.execute(text("PRAGMA table_info(settlements)"))
            columns = [row[1] for row in result.fetchall()]
            column_exists = 'duplicate_block_ids_warning' in columns
        else:
            # PostgreSQL check
            result = db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='settlements' AND column_name='duplicate_block_ids_warning'
            """))
            column_exists = result.fetchone() is not None
        
        if column_exists:
            print("✓ Column 'duplicate_block_ids_warning' already exists in settlements table.")
            return True
        
        print("Adding 'duplicate_block_ids_warning' column to settlements table...")
        
        if DATABASE_URL.startswith("sqlite"):
            # SQLite - use TEXT for JSON
            db.execute(text("ALTER TABLE settlements ADD COLUMN duplicate_block_ids_warning TEXT"))
        else:
            # PostgreSQL - use JSONB for better performance
            db.execute(text("ALTER TABLE settlements ADD COLUMN duplicate_block_ids_warning JSONB"))
        
        db.commit()
        print("✓ Successfully added 'duplicate_block_ids_warning' column to settlements table.")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error adding column: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print(f"Running migration: add duplicate_block_ids_warning column\n")
    success = migrate()
    if success:
        print("\n✓ Migration completed successfully")
    else:
        print("\n✗ Migration failed")
        sys.exit(1)

