"""
Migration script to create accounting journal entries for existing settlements and repairs.
This backfills journal entries retroactively based on settlement_date/repair_date.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.models.tenant import Tenant
from app.models.settlement import Settlement
from app.models.repair import Repair
from app.models.journal_entry import JournalEntry
from app.models.truck import Truck
from app.services.accounting_service import (
    ensure_standard_accounts_exist,
    create_settlement_journal_entry,
    create_repair_journal_entry,
)

def migrate():
    """Create journal entries for all existing settlements and repairs."""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("ACCOUNTING ENTRIES MIGRATION")
        print("=" * 80)
        
        # Get all tenants
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        print(f"\nFound {len(tenants)} active tenant(s)")
        
        total_settlement_count = 0
        total_settlement_errors = 0
        total_repair_count = 0
        total_repair_errors = 0
        
        for tenant in tenants:
            print(f"\n{'=' * 80}")
            print(f"Processing tenant: {tenant.name} (ID: {tenant.id})")
            print(f"{'=' * 80}")
            
            # Ensure standard accounts exist for this tenant
            print(f"\n1. Ensuring standard chart of accounts exist for {tenant.name}...")
            ensure_standard_accounts_exist(db, tenant.id)
            print(f"   ✓ Chart of accounts initialized for {tenant.name}")
            
            # Get all settlements for trucks belonging to this tenant
            print(f"\n2. Processing settlements for {tenant.name}...")
            settlements = db.query(Settlement).join(Truck).filter(
                Truck.tenant_id == tenant.id
            ).order_by(Settlement.settlement_date).all()
            print(f"   Found {len(settlements)} settlements")
            
            settlement_count = 0
            settlement_errors = 0
            
            for settlement in settlements:
                # Check if journal entry already exists for this tenant
                existing = db.query(JournalEntry).filter(
                    JournalEntry.tenant_id == tenant.id,
                    JournalEntry.reference_type == "settlement",
                    JournalEntry.reference_id == settlement.id
                ).first()
                
                if existing:
                    print(f"   ⏭  Settlement {settlement.id} already has journal entry, skipping")
                    continue
                
                try:
                    create_settlement_journal_entry(db, settlement)
                    settlement_count += 1
                    if settlement_count % 10 == 0:
                        print(f"   Processed {settlement_count} settlements...")
                except Exception as e:
                    settlement_errors += 1
                    print(f"   ✗ Error creating journal entry for settlement {settlement.id}: {str(e)}")
            
            print(f"\n   ✓ Created {settlement_count} journal entries for settlements")
            if settlement_errors > 0:
                print(f"   ⚠ {settlement_errors} errors encountered")
            
            total_settlement_count += settlement_count
            total_settlement_errors += settlement_errors
            
            # Get all repairs for trucks belonging to this tenant
            print(f"\n3. Processing repairs for {tenant.name}...")
            repairs = db.query(Repair).join(Truck).filter(
                Truck.tenant_id == tenant.id
            ).order_by(Repair.repair_date).all()
            print(f"   Found {len(repairs)} repairs")
            
            repair_count = 0
            repair_errors = 0
            
            for repair in repairs:
                # Check if journal entry already exists for this tenant
                existing = db.query(JournalEntry).filter(
                    JournalEntry.tenant_id == tenant.id,
                    JournalEntry.reference_type == "repair",
                    JournalEntry.reference_id == repair.id
                ).first()
                
                if existing:
                    print(f"   ⏭  Repair {repair.id} already has journal entry, skipping")
                    continue
                
                # Skip repairs without cost
                if not repair.cost or float(repair.cost) <= 0:
                    print(f"   ⏭  Repair {repair.id} has no cost, skipping")
                    continue
                
                try:
                    create_repair_journal_entry(db, repair)
                    repair_count += 1
                    if repair_count % 10 == 0:
                        print(f"   Processed {repair_count} repairs...")
                except Exception as e:
                    repair_errors += 1
                    print(f"   ✗ Error creating journal entry for repair {repair.id}: {str(e)}")
            
            print(f"\n   ✓ Created {repair_count} journal entries for repairs")
            if repair_errors > 0:
                print(f"   ⚠ {repair_errors} errors encountered")
            
            total_repair_count += repair_count
            total_repair_errors += repair_errors
        
        settlement_count = total_settlement_count
        settlement_errors = total_settlement_errors
        repair_count = total_repair_count
        repair_errors = total_repair_errors
        
        print("\n" + "=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)
        print(f"\nSummary:")
        print(f"  - Settlements processed: {settlement_count}")
        print(f"  - Repairs processed: {repair_count}")
        print(f"  - Total journal entries created: {settlement_count + repair_count}")
        if settlement_errors + repair_errors > 0:
            print(f"  - Errors: {settlement_errors + repair_errors}")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 1
    finally:
        db.close()
    
    return 0

if __name__ == "__main__":
    exit_code = migrate()
    sys.exit(exit_code)

