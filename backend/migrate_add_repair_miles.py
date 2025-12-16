#!/usr/bin/env python3
"""
Migration script to add miles column to repairs table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL

def migrate():
    """Add miles column to repairs table if it doesn't exist"""
    
    is_sqlite = DATABASE_URL.startswith("sqlite")
    
    if is_sqlite:
        import sqlite3
        db_path = os.path.join(backend_dir, "elisgroup.db")
        
        if not os.path.exists(db_path):
            print("Database file not found. Creating new database with all tables...")
            from app.database import Base
            Base.metadata.create_all(bind=engine)
            print("✓ Database created successfully")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if column already exists
            cursor.execute("PRAGMA table_info(repairs)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'miles' not in columns:
                cursor.execute("ALTER TABLE repairs ADD COLUMN miles NUMERIC(10, 2)")
                conn.commit()
                print("✓ Added 'miles' column to repairs table")
            else:
                print("✓ Column 'miles' already exists in repairs table")
        
        except Exception as e:
            print(f"✗ Error migrating database: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        # PostgreSQL
        from sqlalchemy import text
        
        with engine.connect() as conn:
            try:
                # Check if miles column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='repairs' AND column_name='miles'
                """))
                
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE repairs ADD COLUMN miles NUMERIC(10, 2)"))
                    conn.commit()
                    print("✓ Added 'miles' column to repairs table")
                else:
                    print("✓ Column 'miles' already exists in repairs table")
            
            except Exception as e:
                print(f"✗ Error migrating database: {e}")
                conn.rollback()
                raise

if __name__ == "__main__":
    migrate()
    print("\n✓ Migration completed successfully!")


