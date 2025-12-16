"""
Migration script to add 'suv' as a vehicle type option
"""
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.database import DATABASE_URL, SessionLocal
from sqlalchemy import text

def migrate():
    """Add 'suv' to vehicle_type constraint"""
    db = SessionLocal()
    is_sqlite = DATABASE_URL.startswith("sqlite")
    
    try:
        if not is_sqlite:
            # PostgreSQL - need to drop and recreate constraint
            # Check current constraint
            result = db.execute(text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'trucks' 
                AND constraint_name = 'check_vehicle_type'
            """))
            
            if result.fetchone():
                print("Dropping existing check_vehicle_type constraint...")
                db.execute(text("ALTER TABLE trucks DROP CONSTRAINT check_vehicle_type"))
                db.commit()
            
            print("Adding updated check_vehicle_type constraint with 'suv'...")
            db.execute(text("""
                ALTER TABLE trucks 
                ADD CONSTRAINT check_vehicle_type 
                CHECK (vehicle_type IN ('truck', 'trailer', 'suv'))
            """))
            db.commit()
            print("✓ Updated vehicle_type constraint to include 'suv'")
        else:
            # SQLite - constraint is enforced by application layer
            # The model already includes 'suv' in the CheckConstraint
            print("SQLite detected. Constraint is enforced by the application layer.")
            print("✓ Model already includes 'suv' in CheckConstraint")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error during migration: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

