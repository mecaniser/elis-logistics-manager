#!/usr/bin/env python3
"""
Migration script to add expense_categories column to settlements table
"""
import sqlite3
import json
from pathlib import Path

# Get database path
db_path = Path(__file__).parent / "logistics.db"

if not db_path.exists():
    print(f"Database file not found at {db_path}")
    print("The database will be created automatically on next app startup.")
    exit(0)

print(f"Connecting to database: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if expense_categories column already exists
cursor.execute("PRAGMA table_info(settlements)")
columns = [column[1] for column in cursor.fetchall()]

if 'expense_categories' in columns:
    print("✓ Column 'expense_categories' already exists in settlements table.")
else:
    print("Adding 'expense_categories' column to settlements table...")
    try:
        # SQLite doesn't have native JSON type, so we use TEXT
        cursor.execute("ALTER TABLE settlements ADD COLUMN expense_categories TEXT")
        conn.commit()
        print("✓ Successfully added 'expense_categories' column to settlements table.")
    except sqlite3.Error as e:
        print(f"✗ Error adding column: {e}")
        conn.rollback()
        conn.close()
        exit(1)

conn.close()
print("\n✓ Migration completed successfully!")



