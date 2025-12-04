#!/usr/bin/env python3
"""
Migration script to add block_ids column to settlements table (PostgreSQL)
"""
import os
import sys
from pathlib import Path

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import text
from app.database import SessionLocal, DATABASE_URL, engine

def migrate_add_block_ids():
    """Add block_ids column to settlements table if it doesn't exist."""
    db = SessionLocal()
    
    try:
        # Check if column already exists
        if DATABASE_URL.startswith("sqlite"):
            # SQLite check
            result = db.execute(text("PRAGMA table_info(settlements)"))
            columns = [row[1] for row in result.fetchall()]
            column_exists = 'block_ids' in columns
        else:
            # PostgreSQL check
            result = db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='settlements' AND column_name='block_ids'
            """))
            column_exists = result.fetchone() is not None
        
        if column_exists:
            print("✓ Column 'block_ids' already exists in settlements table.")
            return True
        
        print("Adding 'block_ids' column to settlements table...")
        
        if DATABASE_URL.startswith("sqlite"):
            # SQLite - use TEXT for JSON
            db.execute(text("ALTER TABLE settlements ADD COLUMN block_ids TEXT"))
        else:
            # PostgreSQL - use JSONB for better performance
            db.execute(text("ALTER TABLE settlements ADD COLUMN block_ids JSONB"))
        
        db.commit()
        print("✓ Successfully added 'block_ids' column to settlements table.")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error adding column: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print(f"Database: {'PostgreSQL' if 'postgresql' in DATABASE_URL.lower() else 'SQLite'}")
    print(f"Running migration: add block_ids column\n")
    
    success = migrate_add_block_ids()
    
    if success:
        print("\n✓ Migration completed successfully!")
        sys.exit(0)
    else:
        print("\n✗ Migration failed!")
        sys.exit(1)





