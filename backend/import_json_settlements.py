#!/usr/bin/env python3
"""
Simple script to import extracted JSON settlement files into the database.
"""
import sys
import os
import json
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.routers.settlements import upload_settlement_json


def import_json_file(json_path: str, db):
    """Import a single JSON file to the database"""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.dumps(json.load(f))
        
        result = upload_settlement_json(json_data, db)
        return {
            "status": "success",
            "file": json_path,
            "settlements_imported": len(result)
        }
    except Exception as e:
        return {
            "status": "error",
            "file": json_path,
            "error": str(e)
        }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Import extracted JSON settlements to database")
    parser.add_argument("json_path", help="Path to JSON file or directory containing JSON files")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    json_path = Path(args.json_path)
    db = SessionLocal()
    
    try:
        if json_path.is_file():
            # Single file
            if not json_path.suffix == '.json':
                print(f"Error: {json_path} is not a JSON file")
                sys.exit(1)
            
            result = import_json_file(str(json_path), db)
            if result["status"] == "success":
                print(f"✓ Imported {result['settlements_imported']} settlement(s) from {result['file']}")
            else:
                print(f"✗ Error importing {result['file']}: {result['error']}")
                sys.exit(1)
        
        elif json_path.is_dir():
            # Directory of JSON files
            json_files = list(json_path.glob("*.json"))
            
            if not json_files:
                print(f"No JSON files found in {json_path}")
                sys.exit(1)
            
            print(f"Found {len(json_files)} JSON file(s) to import\n")
            
            successful = 0
            failed = 0
            
            for json_file in json_files:
                result = import_json_file(str(json_file), db)
                
                if result["status"] == "success":
                    successful += 1
                    print(f"✓ {json_file.name}: {result['settlements_imported']} settlement(s)")
                else:
                    failed += 1
                    print(f"✗ {json_file.name}: {result['error']}")
            
            print(f"\n{'='*60}")
            print(f"Import complete: {successful} successful, {failed} failed")
            print(f"{'='*60}")
            
            if failed > 0:
                sys.exit(1)
        else:
            print(f"Error: {json_path} does not exist")
            sys.exit(1)
    
    finally:
        db.close()


if __name__ == "__main__":
    main()

