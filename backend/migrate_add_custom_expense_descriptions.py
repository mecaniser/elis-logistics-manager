#!/usr/bin/env python3
"""
Migration script to add custom_expense_descriptions column to settlements table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL

def migrate_add_custom_expense_descriptions():
    """Add custom_expense_descriptions column to settlements table if it doesn't exist"""
    
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
            # Check if column already exists
            cursor.execute("PRAGMA table_info(settlements)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'custom_expense_descriptions' in columns:
                print("✓ Column 'custom_expense_descriptions' already exists in settlements table")
            else:
                # Add the column (SQLite uses TEXT for JSON)
                cursor.execute("ALTER TABLE settlements ADD COLUMN custom_expense_descriptions TEXT")
                conn.commit()
                print("✓ Added 'custom_expense_descriptions' column to settlements table")
        
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
                # Check if column already exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='settlements' AND column_name='custom_expense_descriptions'
                """))
                
                if result.fetchone():
                    print("✓ Column 'custom_expense_descriptions' already exists in settlements table")
                else:
                    # Add the column (PostgreSQL uses JSONB for JSON)
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN custom_expense_descriptions JSONB"))
                    conn.commit()
                    print("✓ Added 'custom_expense_descriptions' column to settlements table")
            
            except Exception as e:
                print(f"✗ Error migrating database: {e}")
                conn.rollback()
                raise

if __name__ == "__main__":
    migrate_add_custom_expense_descriptions()
    print("\n✓ Migration completed successfully!")


