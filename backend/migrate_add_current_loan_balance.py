#!/usr/bin/env python3
"""
Migration script to add current_loan_balance column to trucks table
and initialize it with loan_amount for existing trucks
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL

def migrate_add_current_loan_balance():
    """Add current_loan_balance column and initialize it"""
    
    if "sqlite" in DATABASE_URL.lower():
        # SQLite
        import sqlite3
        
        db_path = DATABASE_URL.replace("sqlite:///", "")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if column already exists
            cursor.execute("PRAGMA table_info(trucks)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'current_loan_balance' in columns:
                print("✓ Column 'current_loan_balance' already exists in trucks table")
            else:
                # Add the column
                cursor.execute("ALTER TABLE trucks ADD COLUMN current_loan_balance NUMERIC(10, 2)")
                print("✓ Added 'current_loan_balance' column to trucks table")
            
            # Initialize current_loan_balance = loan_amount for trucks with loans
            cursor.execute("""
                UPDATE trucks 
                SET current_loan_balance = loan_amount 
                WHERE vehicle_type = 'truck' 
                AND loan_amount IS NOT NULL 
                AND loan_amount > 0
                AND (current_loan_balance IS NULL OR current_loan_balance = 0)
            """)
            updated_count = cursor.rowcount
            print(f"✓ Initialized current_loan_balance for {updated_count} trucks")
            
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
                # Check if column already exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='trucks' AND column_name='current_loan_balance'
                """))
                
                if result.fetchone():
                    print("✓ Column 'current_loan_balance' already exists in trucks table")
                else:
                    # Add the column
                    conn.execute(text("ALTER TABLE trucks ADD COLUMN current_loan_balance NUMERIC(10, 2)"))
                    conn.commit()
                    print("✓ Added 'current_loan_balance' column to trucks table")
                
                # Initialize current_loan_balance = loan_amount for trucks with loans
                result = conn.execute(text("""
                    UPDATE trucks 
                    SET current_loan_balance = loan_amount 
                    WHERE vehicle_type = 'truck' 
                    AND loan_amount IS NOT NULL 
                    AND loan_amount > 0
                    AND (current_loan_balance IS NULL OR current_loan_balance = 0)
                """))
                updated_count = result.rowcount
                conn.commit()
                print(f"✓ Initialized current_loan_balance for {updated_count} trucks")
            
            except Exception as e:
                print(f"✗ Error migrating database: {e}")
                conn.rollback()
                raise

if __name__ == "__main__":
    migrate_add_current_loan_balance()
    print("\n✓ Migration completed successfully!")

