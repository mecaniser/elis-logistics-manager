#!/usr/bin/env python3
"""
Migration script to add VIN column to trucks table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL

def migrate():
    """Add vin column to trucks table if it doesn't exist"""
    
    is_sqlite = DATABASE_URL.startswith("sqlite")
    
    if is_sqlite:
        import sqlite3
        db_path = os.path.join(backend_dir, "elisgroup.db")
        
        if not os.path.exists(db_path):
            print(f"Database file not found at {db_path}")
            print("The database will be created automatically on next app startup.")
            return
        
        print(f"Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if column already exists
            cursor.execute("PRAGMA table_info(trucks)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'vin' not in columns:
                print("Adding 'vin' column to trucks table...")
                cursor.execute("ALTER TABLE trucks ADD COLUMN vin VARCHAR(17)")
                conn.commit()
                print("✓ Successfully added 'vin' column to trucks table.")
            else:
                print("✓ Column 'vin' already exists in trucks table. No migration needed.")
        
        except Exception as e:
            print(f"✗ Error adding column: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        # PostgreSQL
        from sqlalchemy import text
        
        with engine.connect() as conn:
            try:
                # Check if vin column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='trucks' AND column_name='vin'
                """))
                
                if not result.fetchone():
                    print("Adding 'vin' column to trucks table...")
                    conn.execute(text("ALTER TABLE trucks ADD COLUMN vin VARCHAR(17)"))
                    conn.commit()
                    print("✓ Successfully added 'vin' column to trucks table.")
                else:
                    print("✓ Column 'vin' already exists in trucks table. No migration needed.")
            
            except Exception as e:
                print(f"✗ Error adding column: {e}")
                conn.rollback()
                raise
    
    print("Migration completed successfully!")

if __name__ == "__main__":
    migrate()
