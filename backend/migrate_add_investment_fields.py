#!/usr/bin/env python3
"""
Migration script to add investment fields (cash_investment, loan_amount, total_cost) to trucks table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL

def migrate_add_investment_fields():
    """Add investment columns to trucks table if they don't exist"""
    
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
            cursor.execute("PRAGMA table_info(trucks)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'cash_investment' not in columns:
                cursor.execute("ALTER TABLE trucks ADD COLUMN cash_investment NUMERIC(10, 2)")
                print("✓ Added 'cash_investment' column to trucks table")
            else:
                print("✓ Column 'cash_investment' already exists in trucks table")
            
            if 'loan_amount' not in columns:
                cursor.execute("ALTER TABLE trucks ADD COLUMN loan_amount NUMERIC(10, 2)")
                print("✓ Added 'loan_amount' column to trucks table")
            else:
                print("✓ Column 'loan_amount' already exists in trucks table")
            
            if 'total_cost' not in columns:
                cursor.execute("ALTER TABLE trucks ADD COLUMN total_cost NUMERIC(10, 2)")
                print("✓ Added 'total_cost' column to trucks table")
            else:
                print("✓ Column 'total_cost' already exists in trucks table")
            
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
                # Check if cash_investment column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='trucks' AND column_name='cash_investment'
                """))
                
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE trucks ADD COLUMN cash_investment NUMERIC(10, 2)"))
                    conn.commit()
                    print("✓ Added 'cash_investment' column to trucks table")
                else:
                    print("✓ Column 'cash_investment' already exists in trucks table")
                
                # Check if loan_amount column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='trucks' AND column_name='loan_amount'
                """))
                
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE trucks ADD COLUMN loan_amount NUMERIC(10, 2)"))
                    conn.commit()
                    print("✓ Added 'loan_amount' column to trucks table")
                else:
                    print("✓ Column 'loan_amount' already exists in trucks table")
                
                # Check if total_cost column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='trucks' AND column_name='total_cost'
                """))
                
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE trucks ADD COLUMN total_cost NUMERIC(10, 2)"))
                    conn.commit()
                    print("✓ Added 'total_cost' column to trucks table")
                else:
                    print("✓ Column 'total_cost' already exists in trucks table")
            
            except Exception as e:
                print(f"✗ Error migrating database: {e}")
                conn.rollback()
                raise

if __name__ == "__main__":
    migrate_add_investment_fields()
    print("\n✓ Migration completed successfully!")

