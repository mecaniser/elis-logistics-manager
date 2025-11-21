#!/usr/bin/env python3
"""
Migration script to add interest_rate column to trucks table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL

def migrate_add_interest_rate():
    """Add interest_rate column to trucks table if it doesn't exist"""
    
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
            cursor.execute("PRAGMA table_info(trucks)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'interest_rate' not in columns:
                cursor.execute("ALTER TABLE trucks ADD COLUMN interest_rate NUMERIC(5, 4) DEFAULT 0.07")
                # Update existing trucks with loans to have default interest rate
                cursor.execute("UPDATE trucks SET interest_rate = 0.07 WHERE loan_amount IS NOT NULL AND loan_amount > 0 AND interest_rate IS NULL")
                print("✓ Added 'interest_rate' column to trucks table with default 0.07 (7%)")
            else:
                print("✓ Column 'interest_rate' already exists in trucks table")
            
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
                # Check if interest_rate column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='trucks' AND column_name='interest_rate'
                """))
                
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE trucks ADD COLUMN interest_rate NUMERIC(5, 4) DEFAULT 0.07"))
                    # Update existing trucks with loans to have default interest rate
                    conn.execute(text("UPDATE trucks SET interest_rate = 0.07 WHERE loan_amount IS NOT NULL AND loan_amount > 0 AND interest_rate IS NULL"))
                    conn.commit()
                    print("✓ Added 'interest_rate' column to trucks table with default 0.07 (7%)")
                else:
                    print("✓ Column 'interest_rate' already exists in trucks table")
            
            except Exception as e:
                print(f"✗ Error migrating database: {e}")
                conn.rollback()
                raise

if __name__ == "__main__":
    migrate_add_interest_rate()
    print("\n✓ Migration completed successfully!")

