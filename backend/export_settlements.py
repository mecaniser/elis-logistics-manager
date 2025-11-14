#!/usr/bin/env python3
"""
Export settlements data to JSON file, structured for database import
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
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.models.driver import Driver

# Ensure we're using the correct database path
import os
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

def export_settlements(output_file: str = "settlements_export.json"):
    """Export all settlements to JSON file"""
    db = SessionLocal()
    
    try:
        # Get all settlements with related data
        settlements = db.query(Settlement).order_by(Settlement.settlement_date.desc(), Settlement.id.desc()).all()
        
        # Get trucks and drivers for reference
        trucks = {}
        for t in db.query(Truck).all():
            # Parse license_plate_history if it's a JSON string
            history = t.license_plate_history
            if isinstance(history, str):
                try:
                    history = json.loads(history)
                except:
                    history = []
            elif history is None:
                history = []
            
            trucks[t.id] = {
                "id": t.id,
                "name": t.name,
                "license_plate_active": t.license_plate,  # Active license plate
                "license_plate_history": history  # Historical license plates
            }
        drivers = {d.id: {"id": d.id, "name": d.name, "phone": d.phone} 
                  for d in db.query(Driver).all()}
        
        # Structure data for export
        export_data = {
            "export_date": datetime.now().isoformat(),
            "version": "1.0",
            "metadata": {
                "total_settlements": len(settlements),
                "total_trucks": len(trucks),
                "total_drivers": len(drivers)
            },
            "trucks": list(trucks.values()),
            "drivers": list(drivers.values()),
            "settlements": []
        }
        
        # Convert settlements to dict format
        for settlement in settlements:
            settlement_dict = {
                "id": settlement.id,
                "truck_id": settlement.truck_id,
                "truck_name": trucks.get(settlement.truck_id, {}).get("name", f"Truck {settlement.truck_id}"),
                "driver_id": settlement.driver_id,
                "driver_name": drivers.get(settlement.driver_id, {}).get("name") if settlement.driver_id else None,
                "settlement_date": settlement.settlement_date.isoformat() if settlement.settlement_date else None,
                "week_start": settlement.week_start.isoformat() if settlement.week_start else None,
                "week_end": settlement.week_end.isoformat() if settlement.week_end else None,
                "miles_driven": float(settlement.miles_driven) if settlement.miles_driven else None,
                "blocks_delivered": settlement.blocks_delivered,
                "gross_revenue": float(settlement.gross_revenue) if settlement.gross_revenue else None,
                "expenses": float(settlement.expenses) if settlement.expenses else None,
                "expense_categories": settlement.expense_categories if settlement.expense_categories else {},
                "net_profit": float(settlement.net_profit) if settlement.net_profit else None,
                "license_plate": settlement.license_plate,
                "settlement_type": settlement.settlement_type,
                "pdf_file_path": settlement.pdf_file_path,
                "created_at": settlement.created_at.isoformat() if settlement.created_at else None
            }
            
            export_data["settlements"].append(settlement_dict)
        
        # Write to JSON file
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=decimal_to_float)
        
        print(f"✓ Exported {len(settlements)} settlements to {output_path}")
        print(f"  - Trucks: {len(trucks)}")
        print(f"  - Drivers: {len(drivers)}")
        print(f"  - File size: {output_path.stat().st_size / 1024:.2f} KB")
        
        return output_path
        
    except Exception as e:
        print(f"✗ Error exporting settlements: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        db.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Export settlements to JSON")
    parser.add_argument(
        "-o", "--output",
        default="settlements_export.json",
        help="Output JSON file path (default: settlements_export.json)"
    )
    
    args = parser.parse_args()
    export_settlements(args.output)

