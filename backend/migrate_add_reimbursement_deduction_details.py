#!/usr/bin/env python3
"""
Migration script to add reimbursement_details and deduction_details columns to settlements table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL

def migrate_add_reimbursement_deduction_details():
    """Add reimbursement_details and deduction_details columns to settlements table if they don't exist"""
    
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
            # Check if columns already exist
            cursor.execute("PRAGMA table_info(settlements)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'reimbursement_details' not in columns:
                cursor.execute("ALTER TABLE settlements ADD COLUMN reimbursement_details TEXT")
                print("✓ Added 'reimbursement_details' column to settlements table")
            else:
                print("✓ Column 'reimbursement_details' already exists in settlements table")
            
            if 'deduction_details' not in columns:
                cursor.execute("ALTER TABLE settlements ADD COLUMN deduction_details TEXT")
                print("✓ Added 'deduction_details' column to settlements table")
            else:
                print("✓ Column 'deduction_details' already exists in settlements table")
            
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
                # Check if columns already exist
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='settlements' AND column_name IN ('reimbursement_details', 'deduction_details')
                """))
                
                existing_columns = {row[0] for row in result.fetchall()}
                
                if 'reimbursement_details' not in existing_columns:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN reimbursement_details JSONB"))
                    conn.commit()
                    print("✓ Added 'reimbursement_details' column to settlements table")
                else:
                    print("✓ Column 'reimbursement_details' already exists in settlements table")
                
                if 'deduction_details' not in existing_columns:
                    conn.execute(text("ALTER TABLE settlements ADD COLUMN deduction_details JSONB"))
                    conn.commit()
                    print("✓ Added 'deduction_details' column to settlements table")
                else:
                    print("✓ Column 'deduction_details' already exists in settlements table")
            
            except Exception as e:
                print(f"✗ Error migrating database: {e}")
                conn.rollback()
                raise

if __name__ == "__main__":
    migrate_add_reimbursement_deduction_details()
    print("\n✓ Migration completed successfully!")


