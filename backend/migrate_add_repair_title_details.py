#!/usr/bin/env python3
"""
Migration script to add title and details columns to repairs table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL

def migrate_add_repair_title_details():
    """Add title and details columns to repairs table if they don't exist"""
    
    is_sqlite = DATABASE_URL.startswith("sqlite")
    
    if is_sqlite:
        import sqlite3
        db_path = os.path.join(backend_dir, "elisogistics.db")
        
        if not os.path.exists(db_path):
            print("Database file not found. Creating new database with all tables...")
            from app.database import Base
            Base.metadata.create_all(bind=engine)
            print("✓ Database created successfully")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if columns already exist
            cursor.execute("PRAGMA table_info(repairs)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'title' not in columns:
                cursor.execute("ALTER TABLE repairs ADD COLUMN title VARCHAR(200)")
                print("✓ Added 'title' column to repairs table")
            else:
                print("✓ Column 'title' already exists in repairs table")
            
            if 'details' not in columns:
                cursor.execute("ALTER TABLE repairs ADD COLUMN details TEXT")
                print("✓ Added 'details' column to repairs table")
            else:
                print("✓ Column 'details' already exists in repairs table")
            
            conn.commit()
        
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
                # Check if title column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='repairs' AND column_name='title'
                """))
                
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE repairs ADD COLUMN title VARCHAR(200)"))
                    conn.commit()
                    print("✓ Added 'title' column to repairs table")
                else:
                    print("✓ Column 'title' already exists in repairs table")
                
                # Check if details column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='repairs' AND column_name='details'
                """))
                
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE repairs ADD COLUMN details TEXT"))
                    conn.commit()
                    print("✓ Added 'details' column to repairs table")
                else:
                    print("✓ Column 'details' already exists in repairs table")
            
            except Exception as e:
                print(f"✗ Error migrating database: {e}")
                conn.rollback()
                raise

if __name__ == "__main__":
    migrate_add_repair_title_details()
    print("\n✓ Migration completed successfully!")
