#!/usr/bin/env python3
"""
Migration script to add vehicle_type and tag_number columns to trucks table
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL

def migrate_add_vehicle_type_tag_number():
    """Add vehicle_type and tag_number columns to trucks table if they don't exist"""
    
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
            
            if 'vehicle_type' not in columns:
                # Add vehicle_type column (default to 'truck' for existing records)
                cursor.execute("ALTER TABLE trucks ADD COLUMN vehicle_type VARCHAR(20) DEFAULT 'truck'")
                # Update existing records to be 'truck'
                cursor.execute("UPDATE trucks SET vehicle_type = 'truck' WHERE vehicle_type IS NULL")
                print("✓ Added 'vehicle_type' column to trucks table")
            else:
                print("✓ Column 'vehicle_type' already exists in trucks table")
            
            if 'tag_number' not in columns:
                cursor.execute("ALTER TABLE trucks ADD COLUMN tag_number VARCHAR(20)")
                print("✓ Added 'tag_number' column to trucks table")
            else:
                print("✓ Column 'tag_number' already exists in trucks table")
            
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
                # Check if vehicle_type column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='trucks' AND column_name='vehicle_type'
                """))
                
                if not result.fetchone():
                    # Add vehicle_type column with default
                    conn.execute(text("""
                        ALTER TABLE trucks 
                        ADD COLUMN vehicle_type VARCHAR(20) DEFAULT 'truck'
                    """))
                    # Update existing records
                    conn.execute(text("UPDATE trucks SET vehicle_type = 'truck' WHERE vehicle_type IS NULL"))
                    conn.commit()
                    print("✓ Added 'vehicle_type' column to trucks table")
                else:
                    print("✓ Column 'vehicle_type' already exists in trucks table")
                
                # Check if tag_number column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='trucks' AND column_name='tag_number'
                """))
                
                if not result.fetchone():
                    conn.execute(text("ALTER TABLE trucks ADD COLUMN tag_number VARCHAR(20)"))
                    conn.commit()
                    print("✓ Added 'tag_number' column to trucks table")
                else:
                    print("✓ Column 'tag_number' already exists in trucks table")
            
            except Exception as e:
                print(f"✗ Error migrating database: {e}")
                conn.rollback()
                raise

if __name__ == "__main__":
    migrate_add_vehicle_type_tag_number()
    print("\n✓ Migration completed successfully!")

