"""
Migration script to add depreciation fields to trucks table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.database import DATABASE_URL

def migrate_database():
    """Add depreciation fields to trucks table"""
    is_sqlite = DATABASE_URL.startswith("sqlite")
    
    if not is_sqlite:
        # PostgreSQL - use SQLAlchemy
        from sqlalchemy import text
        from app.database import engine
        
        with engine.connect() as connection:
            # Check if columns exist
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'trucks'
            """))
            columns = [row[0] for row in result]
            
            # Add columns if they don't exist
            if 'purchase_date' not in columns:
                print("Adding purchase_date column...")
                connection.execute(text("ALTER TABLE trucks ADD COLUMN purchase_date DATE"))
            
            if 'depreciation_method' not in columns:
                print("Adding depreciation_method column...")
                connection.execute(text("ALTER TABLE trucks ADD COLUMN depreciation_method VARCHAR(20) DEFAULT 'MACRS_5'"))
            
            if 'cost_basis' not in columns:
                print("Adding cost_basis column...")
                connection.execute(text("ALTER TABLE trucks ADD COLUMN cost_basis NUMERIC(10, 2)"))
            
            if 'section_179_deduction' not in columns:
                print("Adding section_179_deduction column...")
                connection.execute(text("ALTER TABLE trucks ADD COLUMN section_179_deduction NUMERIC(10, 2) DEFAULT 0"))
            
            if 'bonus_depreciation' not in columns:
                print("Adding bonus_depreciation column...")
                connection.execute(text("ALTER TABLE trucks ADD COLUMN bonus_depreciation NUMERIC(10, 2) DEFAULT 0"))
            
            connection.commit()
            print("Migration completed successfully!")
        return
    
    # SQLite
    db_path = DATABASE_URL.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(trucks)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add purchase_date if it doesn't exist
        if 'purchase_date' not in columns:
            print("Adding purchase_date column...")
            cursor.execute("ALTER TABLE trucks ADD COLUMN purchase_date DATE")
        
        # Add depreciation_method if it doesn't exist
        if 'depreciation_method' not in columns:
            print("Adding depreciation_method column...")
            cursor.execute("ALTER TABLE trucks ADD COLUMN depreciation_method VARCHAR(20) DEFAULT 'MACRS_5'")
        
        # Add cost_basis if it doesn't exist
        if 'cost_basis' not in columns:
            print("Adding cost_basis column...")
            cursor.execute("ALTER TABLE trucks ADD COLUMN cost_basis NUMERIC(10, 2)")
        
        # Add section_179_deduction if it doesn't exist
        if 'section_179_deduction' not in columns:
            print("Adding section_179_deduction column...")
            cursor.execute("ALTER TABLE trucks ADD COLUMN section_179_deduction NUMERIC(10, 2) DEFAULT 0")
        
        # Add bonus_depreciation if it doesn't exist
        if 'bonus_depreciation' not in columns:
            print("Adding bonus_depreciation column...")
            cursor.execute("ALTER TABLE trucks ADD COLUMN bonus_depreciation NUMERIC(10, 2) DEFAULT 0")
        
        conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()

