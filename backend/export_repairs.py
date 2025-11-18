#!/usr/bin/env python3
"""
Export repairs data to JSON file, structured for database import
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

from app.database import SessionLocal
from app.models.repair import Repair
from app.models.truck import Truck

# Ensure we're using the correct database path
os.chdir(backend_dir)

def decimal_to_float(obj):
    """Convert Decimal to float for JSON serialization"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def date_to_string(obj):
    """Convert date/datetime to string"""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj

def export_repairs(output_file: str = "repairs_export.json"):
    """Export all repairs to JSON file"""
    db = SessionLocal()
    
    try:
        # Get all repairs with related data
        repairs = db.query(Repair).order_by(Repair.repair_date.desc(), Repair.id.desc()).all()
        
        # Get trucks for reference
        trucks = {}
        for t in db.query(Truck).all():
            trucks[t.id] = {
                "id": t.id,
                "name": t.name,
                "license_plate": t.license_plate,
                "vin": t.vin
            }
        
        # Structure data for export
        export_data = {
            "export_date": datetime.now().isoformat(),
            "version": "1.0",
            "metadata": {
                "total_repairs": len(repairs),
                "total_trucks": len(trucks)
            },
            "trucks": list(trucks.values()),
            "repairs": []
        }
        
        # Convert repairs to dict format
        for repair in repairs:
            repair_dict = {
                "id": repair.id,
                "truck_id": repair.truck_id,
                "truck_name": trucks.get(repair.truck_id, {}).get("name", f"Truck {repair.truck_id}"),
                "repair_date": repair.repair_date.isoformat() if repair.repair_date else None,
                "description": repair.description,
                "category": repair.category,
                "cost": float(repair.cost) if repair.cost else None,
                "receipt_path": repair.receipt_path,
                "invoice_number": repair.invoice_number,
                "image_paths": repair.image_paths if repair.image_paths else [],
                "created_at": repair.created_at.isoformat() if repair.created_at else None
            }
            export_data["repairs"].append(repair_dict)
        
        # Write to JSON file
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=decimal_to_float, ensure_ascii=False)
        
        print(f"✓ Exported {len(repairs)} repairs to {output_path}")
        print(f"  Trucks: {len(trucks)}")
        print(f"  Total repair cost: ${sum(r.cost or 0 for r in repairs):,.2f}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error exporting repairs: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Export repairs data to JSON file"
    )
    parser.add_argument(
        "-o", "--output",
        default="repairs_export.json",
        help="Output JSON file path (default: repairs_export.json)"
    )
    
    args = parser.parse_args()
    
    success = export_repairs(args.output)
    sys.exit(0 if success else 1)


