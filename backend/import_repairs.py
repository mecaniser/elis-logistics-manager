#!/usr/bin/env python3
"""
Import repairs from JSON file into database
"""
import json
import sys
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import SessionLocal, engine, Base
from app.models.repair import Repair
from app.models.truck import Truck
from sqlalchemy.exc import IntegrityError

def import_repairs(input_file: str, skip_existing: bool = True, clear_existing: bool = False):
    """Import repairs from JSON file"""
    db = SessionLocal()
    
    try:
        # Ensure tables exist
        Base.metadata.create_all(bind=engine)
        
        # Read JSON file
        input_path = Path(input_file)
        if not input_path.exists():
            print(f"✗ File not found: {input_path}")
            return False
        
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        repairs_data = data.get("repairs", [])
        if not repairs_data:
            print("✗ No repairs found in JSON file")
            return False
        
        print(f"Found {len(repairs_data)} repairs in JSON file")
        
        # Clear existing repairs if requested
        if clear_existing:
            print("⚠️  Clearing all existing repairs...")
            deleted_count = db.query(Repair).delete()
            db.commit()
            print(f"✓ Deleted {deleted_count} existing repairs")
        
        # Verify trucks exist
        trucks_map = {}
        for truck_data in data.get("trucks", []):
            truck = db.query(Truck).filter(Truck.id == truck_data["id"]).first()
            if not truck:
                print(f"⚠ Warning: Truck ID {truck_data['id']} ({truck_data.get('name')}) not found in database")
            else:
                trucks_map[truck_data["id"]] = truck
        
        # Import repairs
        imported = 0
        skipped = 0
        errors = 0
        
        print(f"\nImporting repairs...")
        
        for idx, repair_data in enumerate(repairs_data, 1):
            try:
                # Check if repair already exists
                # Method 1: Check by invoice_number (most reliable if available)
                if skip_existing and not clear_existing:
                    existing = None
                    invoice_number = repair_data.get("invoice_number")
                    if invoice_number:
                        existing = db.query(Repair).filter(
                            Repair.truck_id == repair_data["truck_id"],
                            Repair.invoice_number == invoice_number
                        ).first()
                    
                    # Method 2: Check by truck_id + repair_date + cost (fallback)
                    if not existing:
                        repair_date = None
                        if repair_data.get("repair_date"):
                            repair_date = datetime.fromisoformat(repair_data["repair_date"]).date()
                        cost = None
                        if repair_data.get("cost") is not None:
                            cost = Decimal(str(repair_data["cost"]))
                        
                        if repair_date and cost:
                            existing = db.query(Repair).filter(
                                Repair.truck_id == repair_data["truck_id"],
                                Repair.repair_date == repair_date,
                                Repair.cost == cost
                            ).first()
                    
                    if existing:
                        skipped += 1
                        continue
                
                # Validate truck exists
                if repair_data["truck_id"] not in trucks_map:
                    print(f"  ⚠ Skipping repair {idx}: Truck ID {repair_data['truck_id']} not found")
                    errors += 1
                    continue
                
                # Parse dates
                repair_date = None
                if repair_data.get("repair_date"):
                    repair_date = datetime.fromisoformat(repair_data["repair_date"]).date()
                
                # Parse cost
                cost = None
                if repair_data.get("cost") is not None:
                    cost = Decimal(str(repair_data["cost"]))
                
                # Create repair object
                repair = Repair(
                    truck_id=repair_data["truck_id"],
                    repair_date=repair_date,
                    description=repair_data.get("description"),
                    category=repair_data.get("category"),
                    cost=cost,
                    receipt_path=repair_data.get("receipt_path"),
                    invoice_number=repair_data.get("invoice_number"),
                    image_paths=repair_data.get("image_paths", [])
                )
                
                db.add(repair)
                db.commit()
                imported += 1
                
                if imported % 10 == 0:
                    print(f"  Progress: {idx}/{len(repairs_data)} (imported {imported})")
                
            except IntegrityError as e:
                db.rollback()
                print(f"  ✗ Error importing repair {idx}: {e}")
                errors += 1
            except Exception as e:
                db.rollback()
                print(f"  ✗ Error importing repair {idx}: {e}")
                import traceback
                traceback.print_exc()
                errors += 1
        
        print(f"\n{'='*60}")
        print(f"✓ Import complete:")
        print(f"  - Imported: {imported}")
        print(f"  - Skipped: {skipped}")
        print(f"  - Errors: {errors}")
        print(f"{'='*60}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error importing repairs: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Import repairs from JSON file into database"
    )
    parser.add_argument(
        "input_file",
        help="Input JSON file path"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip existing repairs (default behavior)"
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        default=False,
        help="Delete all existing repairs before import"
    )
    
    args = parser.parse_args()
    
    # Validate flags
    if args.clear_existing:
        args.skip_existing = False
    
    success = import_repairs(
        args.input_file,
        skip_existing=args.skip_existing,
        clear_existing=args.clear_existing
    )
    
    sys.exit(0 if success else 1)


