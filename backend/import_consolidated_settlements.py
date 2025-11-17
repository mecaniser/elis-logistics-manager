#!/usr/bin/env python3
"""
Import consolidated settlements JSON file into database
One-time bulk import for historical settlement data
"""
import json
import sys
import os
import argparse
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import SessionLocal, engine, Base
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.models.driver import Driver
from app.models.repair import Repair
from sqlalchemy.exc import IntegrityError


def find_truck_by_license_plate(db, license_plate: str):
    """
    Find truck by license plate, checking both current plate and history.
    Reuses logic from upload_settlement_json endpoint.
    """
    if not license_plate:
        return None
    
    # Try exact match first
    truck = db.query(Truck).filter(Truck.license_plate == license_plate).first()
    
    # If not found, check license plate history (stored as JSON array)
    if not truck:
        trucks = db.query(Truck).all()
        for t in trucks:
            history = t.license_plate_history
            if isinstance(history, str):
                try:
                    history = json.loads(history)
                except:
                    history = []
            elif history is None:
                history = []
            
            if license_plate in history or license_plate == t.license_plate:
                truck = t
                break
    
    return truck


def transform_settlement_data(settlement_json: dict, db) -> dict:
    """
    Transform consolidated JSON format to database format.
    Reuses logic from upload_settlement_json endpoint.
    """
    metadata = settlement_json.get("metadata", {})
    revenue = settlement_json.get("revenue", {})
    expenses = settlement_json.get("expenses", {})
    metrics = settlement_json.get("metrics", {})
    driver_pay = settlement_json.get("driver_pay", {})
    
    # Parse dates
    settlement_date = None
    week_start = None
    week_end = None
    
    if metadata.get("settlement_date"):
        settlement_date = datetime.fromisoformat(metadata["settlement_date"]).date()
    if metadata.get("week_start"):
        week_start = datetime.fromisoformat(metadata["week_start"]).date()
    if metadata.get("week_end"):
        week_end = datetime.fromisoformat(metadata["week_end"]).date()
    
    # Determine truck_id from license plate
    license_plate = metadata.get("license_plate")
    truck = find_truck_by_license_plate(db, license_plate)
    
    if not truck:
        raise ValueError(f"Could not find truck with license plate '{license_plate}'")
    
    # Build expense categories
    expense_categories = expenses.get("categories", {}).copy()
    if driver_pay.get("driver_pay"):
        expense_categories["driver_pay"] = driver_pay["driver_pay"]
    if driver_pay.get("payroll_fee"):
        expense_categories["payroll_fee"] = driver_pay["payroll_fee"]
    
    # Convert to database format
    settlement_data = {
        "truck_id": truck.id,
        "driver_id": metadata.get("driver_id"),
        "settlement_date": settlement_date,
        "week_start": week_start,
        "week_end": week_end,
        "miles_driven": Decimal(str(metrics.get("miles_driven"))) if metrics.get("miles_driven") else None,
        "blocks_delivered": metrics.get("blocks_delivered"),
        "gross_revenue": Decimal(str(revenue.get("gross_revenue"))) if revenue.get("gross_revenue") else None,
        "expenses": Decimal(str(expenses.get("total_expenses"))) if expenses.get("total_expenses") else None,
        "expense_categories": expense_categories,
        "net_profit": Decimal(str(revenue.get("net_profit"))) if revenue.get("net_profit") else None,
        "license_plate": license_plate,
        "settlement_type": metadata.get("settlement_type"),
        "pdf_file_path": None  # No PDF stored for consolidated imports
    }
    
    return settlement_data


def ensure_trucks_exist(db):
    """
    Ensure trucks exist in database. Create them if they don't exist.
    Based on known truck-to-plate mapping:
    - Truck 417: VW9327, VV9952
    - Truck 418: VW9328, VW1503
    """
    trucks_to_create = [
        {
            "name": "Volvo 417",
            "license_plate": "VW9327",
            "license_plate_history": ["VW9327", "VV9952"]
        },
        {
            "name": "Volvo 418",
            "license_plate": "VW9328",
            "license_plate_history": ["VW9328", "VW1503"]
        }
    ]
    
    created_count = 0
    for truck_data in trucks_to_create:
        # Check if truck exists by name
        existing = db.query(Truck).filter(Truck.name == truck_data["name"]).first()
        if not existing:
            # Create truck
            truck = Truck(**truck_data)
            db.add(truck)
            created_count += 1
            print(f"  Created truck: {truck_data['name']} (plate: {truck_data['license_plate']})")
        else:
            # Update license plate history if needed
            current_plate = existing.license_plate
            history = existing.license_plate_history or []
            
            # Ensure all plates are in history
            for plate in truck_data["license_plate_history"]:
                if plate not in history:
                    history.append(plate)
            
            # Update current plate if not set or if it's different
            if not current_plate:
                existing.license_plate = truck_data["license_plate"]
            elif current_plate not in truck_data["license_plate_history"]:
                # Current plate not in expected history, update it
                existing.license_plate = truck_data["license_plate"]
            
            existing.license_plate_history = history
    
    if created_count > 0:
        db.commit()
        print(f"✓ Created {created_count} truck(s)")
    else:
        print(f"✓ All trucks already exist")


def import_consolidated_settlements(
    input_file: str,
    clear_existing: bool = False,
    update_existing: bool = False,
    skip_existing: bool = True
):
    """
    Import settlements from consolidated JSON file into database.
    
    Args:
        input_file: Path to consolidated JSON file
        clear_existing: If True, delete all existing settlements before import
        update_existing: If True, update existing settlements (truck_id + settlement_date match)
        skip_existing: If True, skip existing settlements (default)
    """
    # Ensure database tables exist
    print("Ensuring database tables exist...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    try:
        # Ensure trucks exist
        print("\nEnsuring trucks exist in database...")
        ensure_trucks_exist(db)
        
        # Read JSON file
        input_path = Path(input_file)
        if not input_path.exists():
            print(f"✗ File not found: {input_path}")
            return False
        
        print(f"\nReading consolidated settlements from: {input_path}")
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        settlements_data = data.get("settlements", [])
        if not settlements_data:
            print("✗ No settlements found in JSON file")
            return False
        
        print(f"Found {len(settlements_data)} settlements in JSON file")
        
        # Clear existing settlements if requested
        if clear_existing:
            print("\n⚠️  Clearing all existing settlements...")
            deleted_count = db.query(Settlement).delete()
            db.commit()
            print(f"✓ Deleted {deleted_count} existing settlements")
        
        # Import settlements
        imported = 0
        updated = 0
        skipped = 0
        errors = 0
        error_details = []
        
        print(f"\nImporting settlements...")
        
        for idx, settlement_json in enumerate(settlements_data, 1):
            try:
                # Transform JSON to database format
                settlement_data = transform_settlement_data(settlement_json, db)
                
                # Check for existing settlement
                existing = None
                if settlement_data["settlement_date"]:
                    existing = db.query(Settlement).filter(
                        Settlement.truck_id == settlement_data["truck_id"],
                        Settlement.settlement_date == settlement_data["settlement_date"]
                    ).first()
                
                if existing:
                    if skip_existing:
                        skipped += 1
                        if idx % 10 == 0:
                            print(f"  Progress: {idx}/{len(settlements_data)} (skipped {skipped} duplicates)")
                        continue
                    elif update_existing:
                        # Update existing settlement
                        for key, value in settlement_data.items():
                            setattr(existing, key, value)
                        db.commit()
                        updated += 1
                        if idx % 10 == 0:
                            print(f"  Progress: {idx}/{len(settlements_data)} (updated {updated})")
                        continue
                    else:
                        # Skip if not updating
                        skipped += 1
                        continue
                
                # Create new settlement
                db_settlement = Settlement(**settlement_data)
                db.add(db_settlement)
                db.commit()
                imported += 1
                
                if idx % 10 == 0:
                    print(f"  Progress: {idx}/{len(settlements_data)} (imported {imported})")
                
            except ValueError as e:
                # Missing truck - report but continue
                errors += 1
                license_plate = settlement_json.get("metadata", {}).get("license_plate", "unknown")
                error_msg = f"Settlement {idx} (plate: {license_plate}): {str(e)}"
                error_details.append(error_msg)
                db.rollback()
            except IntegrityError as e:
                errors += 1
                error_msg = f"Settlement {idx}: Database integrity error - {str(e)}"
                error_details.append(error_msg)
                db.rollback()
            except Exception as e:
                errors += 1
                license_plate = settlement_json.get("metadata", {}).get("license_plate", "unknown")
                error_msg = f"Settlement {idx} (plate: {license_plate}): {str(e)}"
                error_details.append(error_msg)
                db.rollback()
        
        print(f"\n{'='*60}")
        print(f"✓ Import complete:")
        print(f"  - Imported: {imported}")
        if update_existing:
            print(f"  - Updated: {updated}")
        if skip_existing or not update_existing:
            print(f"  - Skipped: {skipped}")
        print(f"  - Errors: {errors}")
        
        if error_details:
            print(f"\n⚠️  Error details:")
            for error in error_details[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(error_details) > 10:
                print(f"  ... and {len(error_details) - 10} more errors")
        
        return True
        
    except Exception as e:
        print(f"✗ Error importing settlements: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import consolidated settlements JSON file into database"
    )
    parser.add_argument(
        "input_file",
        help="Path to consolidated settlements JSON file"
    )
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Delete all existing settlements before import"
    )
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update existing settlements instead of skipping them"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip existing settlements (default behavior)"
    )
    
    args = parser.parse_args()
    
    # Validate flags
    if args.clear_existing and args.update_existing:
        print("✗ Error: Cannot use both --clear-existing and --update-existing")
        sys.exit(1)
    
    if args.update_existing:
        args.skip_existing = False
    
    success = import_consolidated_settlements(
        args.input_file,
        clear_existing=args.clear_existing,
        update_existing=args.update_existing,
        skip_existing=args.skip_existing
    )
    
    sys.exit(0 if success else 1)

