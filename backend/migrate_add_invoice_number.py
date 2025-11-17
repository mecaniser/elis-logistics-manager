#!/usr/bin/env python3
"""
Migration script to add invoice_number column to repairs table
"""
import sqlite3
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, Base
from app.models.repair import Repair

def migrate_add_invoice_number():
    """Add invoice_number column to repairs table if it doesn't exist"""
    db_path = os.path.join(backend_dir, "elisogistics.db")
    
    if not os.path.exists(db_path):
        print("Database file not found. Creating new database with all tables...")
        Base.metadata.create_all(bind=engine)
        print("✓ Database created successfully")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(repairs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'invoice_number' in columns:
            print("✓ Column 'invoice_number' already exists in repairs table")
        else:
            # Add the column
            cursor.execute("ALTER TABLE repairs ADD COLUMN invoice_number VARCHAR(50)")
            conn.commit()
            print("✓ Added 'invoice_number' column to repairs table")
        
    except Exception as e:
        print(f"✗ Error migrating database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_add_invoice_number()

