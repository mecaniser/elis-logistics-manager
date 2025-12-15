#!/usr/bin/env python3
"""
Backfill script to check all existing settlements for duplicate block IDs
and populate the duplicate_block_ids_warning field.
"""
import os
import sys
from pathlib import Path

# Add backend directory to path
BASE_DIR = Path(__file__).resolve().parents[0]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.database import SessionLocal
from app.models.settlement import Settlement
from app.utils.block_id_validator import validate_block_ids

def backfill_duplicate_warnings():
    """Check all existing settlements and populate duplicate_block_ids_warning field."""
    db = SessionLocal()
    
    try:
        # Get all settlements
        settlements = db.query(Settlement).all()
        total = len(settlements)
        flagged = 0
        
        print(f"Checking {total} settlements for duplicate block IDs...\n")
        
        for idx, settlement in enumerate(settlements, 1):
            if not settlement.block_ids:
                continue
            
            # Check for duplicates (excluding this settlement itself)
            has_duplicates, warning_msg, duplicates = validate_block_ids(
                settlement.block_ids,
                db,
                exclude_settlement_id=settlement.id
            )
            
            if has_duplicates:
                duplicate_block_ids = sorted(set(d["block_id"] for d in duplicates))
                settlement.duplicate_block_ids_warning = {
                    "has_duplicates": True,
                    "duplicate_block_ids": duplicate_block_ids,
                    "conflicting_settlements": duplicates,
                    "warning_message": warning_msg
                }
                flagged += 1
                print(f"[{idx}/{total}] ✓ Settlement #{settlement.id} (Truck {settlement.truck_id}, {settlement.settlement_date}): Flagged {len(duplicate_block_ids)} duplicate block ID(s)")
            else:
                # Clear any existing warning if no duplicates found
                if settlement.duplicate_block_ids_warning:
                    settlement.duplicate_block_ids_warning = None
            
            # Commit every 10 settlements to avoid long transactions
            if idx % 10 == 0:
                db.commit()
        
        # Final commit
        db.commit()
        
        print(f"\n✓ Backfill completed:")
        print(f"  - Total settlements checked: {total}")
        print(f"  - Settlements flagged with duplicates: {flagged}")
        print(f"  - Settlements with no duplicates: {total - flagged}")
        
        return True
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error during backfill: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("Running backfill: populate duplicate_block_ids_warning for existing settlements\n")
    success = backfill_duplicate_warnings()
    if success:
        print("\n✓ Backfill completed successfully")
    else:
        print("\n✗ Backfill failed")
        sys.exit(1)

