#!/usr/bin/env python3
"""
Migration script to add VIN column to trucks table
"""
import sqlite3
import os
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

# Check if vin column already exists
cursor.execute("PRAGMA table_info(trucks)")
columns = [column[1] for column in cursor.fetchall()]

if 'vin' in columns:
    print("✓ Column 'vin' already exists in trucks table. No migration needed.")
else:
    print("Adding 'vin' column to trucks table...")
    try:
        cursor.execute("ALTER TABLE trucks ADD COLUMN vin VARCHAR(17)")
        conn.commit()
        print("✓ Successfully added 'vin' column to trucks table.")
    except sqlite3.Error as e:
        print(f"✗ Error adding column: {e}")
        conn.rollback()
        exit(1)

conn.close()
print("Migration completed successfully!")

