#!/usr/bin/env python3
"""
Import settlements from JSON file into database
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

from app.database import SessionLocal, engine
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.models.driver import Driver
from sqlalchemy.exc import IntegrityError

def import_settlements(input_file: str, skip_existing: bool = True):
    """Import settlements from JSON file"""
    db = SessionLocal()
    
    try:
        # Read JSON file
        input_path = Path(input_file)
        if not input_path.exists():
            print(f"✗ File not found: {input_path}")
            return False
        
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        settlements_data = data.get("settlements", [])
        if not settlements_data:
            print("✗ No settlements found in JSON file")
            return False
        
        print(f"Found {len(settlements_data)} settlements in JSON file")
        
        # Verify trucks exist
        trucks_map = {}
        for truck_data in data.get("trucks", []):
            truck = db.query(Truck).filter(Truck.id == truck_data["id"]).first()
            if not truck:
                print(f"⚠ Warning: Truck ID {truck_data['id']} ({truck_data.get('name')}) not found in database")
            else:
                trucks_map[truck_data["id"]] = truck
        
        # Import settlements
        imported = 0
        skipped = 0
        errors = 0
        
        for settlement_data in settlements_data:
            try:
                # Check if settlement already exists
                existing = db.query(Settlement).filter(
                    Settlement.truck_id == settlement_data["truck_id"],
                    Settlement.settlement_date == datetime.fromisoformat(settlement_data["settlement_date"]).date()
                ).first()
                
                if existing and skip_existing:
                    skipped += 1
                    continue
                
                # Create settlement object
                settlement = Settlement(
                    truck_id=settlement_data["truck_id"],
                    driver_id=settlement_data.get("driver_id"),
                    settlement_date=datetime.fromisoformat(settlement_data["settlement_date"]).date(),
                    week_start=datetime.fromisoformat(settlement_data["week_start"]).date() if settlement_data.get("week_start") else None,
                    week_end=datetime.fromisoformat(settlement_data["week_end"]).date() if settlement_data.get("week_end") else None,
                    miles_driven=Decimal(str(settlement_data["miles_driven"])) if settlement_data.get("miles_driven") else None,
                    blocks_delivered=settlement_data.get("blocks_delivered"),
                    gross_revenue=Decimal(str(settlement_data["gross_revenue"])) if settlement_data.get("gross_revenue") else None,
                    expenses=Decimal(str(settlement_data["expenses"])) if settlement_data.get("expenses") else None,
                    expense_categories=settlement_data.get("expense_categories", {}),
                    net_profit=Decimal(str(settlement_data["net_profit"])) if settlement_data.get("net_profit") else None,
                    license_plate=settlement_data.get("license_plate"),
                    settlement_type=settlement_data.get("settlement_type"),
                    pdf_file_path=settlement_data.get("pdf_file_path")
                )
                
                db.add(settlement)
                db.commit()
                imported += 1
                
            except IntegrityError as e:
                db.rollback()
                errors += 1
                print(f"  ✗ Error importing settlement {settlement_data.get('id')}: {e}")
            except Exception as e:
                db.rollback()
                errors += 1
                print(f"  ✗ Error importing settlement {settlement_data.get('id')}: {e}")
        
        print(f"\n✓ Import complete:")
        print(f"  - Imported: {imported}")
        print(f"  - Skipped: {skipped}")
        print(f"  - Errors: {errors}")
        
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
    import argparse
    
    parser = argparse.ArgumentParser(description="Import settlements from JSON")
    parser.add_argument(
        "input_file",
        help="Input JSON file path"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing settlements (default: skip existing)"
    )
    
    args = parser.parse_args()
    import_settlements(args.input_file, skip_existing=not args.force)

