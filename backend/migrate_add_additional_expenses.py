#!/usr/bin/env python3
"""
Migration script to add additional_expenses column to trucks table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL

def migrate():
    """Add additional_expenses column to trucks table if it doesn't exist"""
    
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
            cursor.execute("PRAGMA table_info(trucks)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'additional_expenses' not in columns:
                cursor.execute("ALTER TABLE trucks ADD COLUMN additional_expenses TEXT")
                print("✓ Added 'additional_expenses' column to trucks table")
            else:
                print("✓ Column 'additional_expenses' already exists in trucks table")
            
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
                # Check if additional_expenses column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='trucks' AND column_name='additional_expenses'
                """))
                
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE trucks ADD COLUMN additional_expenses JSONB"))
                    conn.commit()
                    print("✓ Added 'additional_expenses' column to trucks table")
                else:
                    print("✓ Column 'additional_expenses' already exists in trucks table")
            
            except Exception as e:
                print(f"✗ Error migrating database: {e}")
                conn.rollback()
                raise

if __name__ == "__main__":
    migrate()

