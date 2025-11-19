#!/usr/bin/env python3
"""
Check which trucks are missing VIN numbers
"""
import sys
import os
from pathlib import Path

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import SessionLocal
from app.models.truck import Truck

def check_truck_vins():
    """Check which trucks are missing VIN numbers"""
    db = SessionLocal()
    
    try:
        trucks = db.query(Truck).all()
        
        print("=" * 60)
        print("Truck VIN Status Report")
        print("=" * 60)
        print()
        
        trucks_without_vin = []
        trucks_with_vin = []
        
        for truck in trucks:
            if not truck.vin or truck.vin.strip() == '':
                trucks_without_vin.append(truck)
            else:
                trucks_with_vin.append(truck)
        
        print(f"Total Trucks: {len(trucks)}")
        print(f"Trucks WITH VIN: {len(trucks_with_vin)}")
        print(f"Trucks WITHOUT VIN: {len(trucks_without_vin)}")
        print()
        
        if trucks_without_vin:
            print("⚠️  Trucks Missing VIN:")
            print("-" * 60)
            for truck in trucks_without_vin:
                print(f"  ID: {truck.id}")
                print(f"  Name: {truck.name}")
                print(f"  License Plate: {truck.license_plate or 'N/A'}")
                print()
        
        if trucks_with_vin:
            print("✓ Trucks WITH VIN:")
            print("-" * 60)
            for truck in trucks_with_vin:
                print(f"  ID: {truck.id}")
                print(f"  Name: {truck.name}")
                print(f"  VIN: {truck.vin}")
                print(f"  License Plate: {truck.license_plate or 'N/A'}")
                print()
        
        print("=" * 60)
        print()
        print("To add VINs:")
        print("1. Go to the Trucks page in the UI")
        print("2. Click 'Edit' on each truck missing a VIN")
        print("3. Enter the VIN (17 characters)")
        print("4. Click 'Update'")
        print()
        
        return len(trucks_without_vin) == 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = check_truck_vins()
    sys.exit(0 if success else 1)

