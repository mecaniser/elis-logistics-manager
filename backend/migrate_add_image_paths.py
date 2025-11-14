#!/usr/bin/env python3
"""
Migration script to add image_paths column to repairs table
"""
import sqlite3
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

# Check if image_paths column already exists
cursor.execute("PRAGMA table_info(repairs)")
columns = [column[1] for column in cursor.fetchall()]

if 'image_paths' in columns:
    print("✓ Column 'image_paths' already exists in repairs table.")
else:
    print("Adding 'image_paths' column to repairs table...")
    try:
        # SQLite doesn't have native JSON type, so we use TEXT
        cursor.execute("ALTER TABLE repairs ADD COLUMN image_paths TEXT")
        conn.commit()
        print("✓ Successfully added 'image_paths' column to repairs table.")
    except sqlite3.Error as e:
        print(f"✗ Error adding column: {e}")
        conn.rollback()
        conn.close()
        exit(1)

conn.close()
print("\n✓ Migration completed successfully!")

