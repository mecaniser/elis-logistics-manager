#!/usr/bin/env python3
"""
Migration script to simplify chart of accounts for Elis Logistics LLC.

This script:
1. Ensures all accounts for Elis Logistics LLC have truck_id = NULL (shared accounts)
2. Ensures minimal accounts exist (Trailer Rental Income, Trailer Expenses, Section 179)
3. Deactivates old unused accounts (Fuel, Dispatch Fees, Insurance, etc.) that Elis Logistics doesn't use
4. Updates journal entries to use truck_id = NULL for Elis Logistics

This migration is idempotent and safe to run multiple times.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import SessionLocal, engine
from app.models.tenant import Tenant
from app.models.chart_of_accounts import ChartOfAccount
from app.models.journal_entry import JournalEntry
from app.models.journal_entry_line import JournalEntryLine
from app.services.accounting_service import uses_per_asset_accounting, get_or_create_account

def migrate():
    """Simplify accounts for Elis Logistics LLC"""
    db = SessionLocal()
    
    try:
        print("=" * 80)
        print("SIMPLIFY ELIS LOGISTICS ACCOUNTS MIGRATION")
        print("=" * 80)
        
        # Find Elis Logistics LLC tenant
        elis_tenant = db.query(Tenant).filter(
            Tenant.name.ilike("%elis logistics%")
        ).first()
        
        if not elis_tenant:
            print("\n⚠ No tenant found matching 'Elis Logistics'. Skipping migration.")
            print("   This migration only applies to Elis Logistics LLC.")
            return 0
        
        print(f"\nFound tenant: {elis_tenant.name} (ID: {elis_tenant.id})")
        
        # Verify this tenant doesn't use per-asset accounting
        if uses_per_asset_accounting(elis_tenant):
            print(f"\n⚠ Tenant '{elis_tenant.name}' uses per-asset accounting. Skipping migration.")
            print("   This migration only applies to tenants with shared accounts.")
            return 0
        
        print(f"✓ Tenant uses shared accounts (truck_id = NULL)")
        
        # Step 1: Ensure all accounts have truck_id = NULL
        print("\n1. Ensuring all accounts have truck_id = NULL...")
        accounts_with_truck_id = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == elis_tenant.id,
            ChartOfAccount.truck_id.isnot(None)
        ).all()
        
        if accounts_with_truck_id:
            print(f"   Found {len(accounts_with_truck_id)} accounts with truck_id set")
            for account in accounts_with_truck_id:
                print(f"   - Updating account {account.code} ({account.name})")
                account.truck_id = None
            db.commit()
            print(f"   ✓ Updated {len(accounts_with_truck_id)} accounts")
        else:
            print("   ✓ All accounts already have truck_id = NULL")
        
        # Step 2: Ensure minimal accounts exist
        print("\n2. Ensuring minimal accounts exist...")
        minimal_accounts = [
            ("1000", "Cash", "Asset"),
            ("1500", "Vehicles & Equipment", "Asset"),
            ("1600", "Accumulated Depreciation - Vehicles", "Asset"),
            ("2100", "Loans Payable", "Liability"),
            ("2200", "Taxes Payable", "Liability"),
            ("3000", "Owner Equity", "Equity"),
            ("3100", "Retained Earnings", "Equity"),
            ("4000", "Settlement Income", "Revenue"),
            ("4100", "Trailer Rental Income", "Revenue"),  # New
            ("5100", "Maintenance & Repairs", "Expense"),
            ("5200", "Trailer Expenses", "Expense"),  # New
            ("5300", "Interest Expense", "Expense"),
            ("5400", "Depreciation Expense", "Expense"),
            ("5500", "Section 179 Deduction", "Expense"),  # New
        ]
        
        created_count = 0
        for code, name, account_type in minimal_accounts:
            account = get_or_create_account(db, code, name, account_type, elis_tenant.id, parent_id=None, truck_id=None)
            if account.truck_id is None:  # Only count if it's correctly set
                created_count += 1
        
        print(f"   ✓ Ensured {len(minimal_accounts)} minimal accounts exist")
        
        # Step 3: Handle account code conflicts and deactivate unused accounts
        print("\n3. Handling account code conflicts and deactivating unused accounts...")
        
        # Check for conflicts: old account codes that are now used for different purposes
        # Old: 5200 = Insurance, New: 5200 = Trailer Expenses
        # Old: 5300 = Dispatch Fees, New: 5300 = Interest Expense  
        # Old: 5400 = Payroll Fees, New: 5400 = Depreciation Expense
        conflict_codes = {
            "5200": ("Insurance", "Trailer Expenses"),
            "5300": ("Dispatch Fees", "Interest Expense"),
            "5400": ("Payroll Fees", "Depreciation Expense"),
        }
        
        conflict_resolved = 0
        for code, (old_name, new_name) in conflict_codes.items():
            account = db.query(ChartOfAccount).filter(
                ChartOfAccount.tenant_id == elis_tenant.id,
                ChartOfAccount.code == code,
                ChartOfAccount.truck_id.is_(None)
            ).first()
            
            if account and account.name != new_name:
                # Check if old account is referenced
                line_count = db.query(JournalEntryLine).filter(
                    JournalEntryLine.account_id == account.id
                ).count()
                
                if line_count == 0:
                    # Old account not used - rename it to match new purpose
                    print(f"   - Renaming {code} from '{account.name}' to '{new_name}'")
                    account.name = new_name
                    conflict_resolved += 1
                else:
                    # Old account is used - deactivate it and create new one
                    print(f"   - Old account {code} ({account.name}) is in use ({line_count} lines)")
                    print(f"     Deactivating old account, new account '{new_name}' will be created")
                    account.is_active = False
                    conflict_resolved += 1
        
        if conflict_resolved > 0:
            db.commit()
        
        # Deactivate other unused accounts (after committing conflict resolution)
        unused_account_codes = [
            "5000",  # Fuel (old)
            "6001",  # Fuel Expense
            "6002",  # Dispatch Fee Expense
            "6003",  # Insurance Expense
            "6004",  # Safety Expense
            "6005",  # Prepass Expense
            "6006",  # IFTA Expense
            "6007",  # Driver Pay Expense
            "6008",  # Payroll Fee Expense
            "6010",  # Parking Expense
            "6012",  # Decals Expense
        ]
        
        # Only deactivate accounts that aren't in use (no journal entry lines reference them)
        deactivated_count = 0
        for code in unused_account_codes:
            account = db.query(ChartOfAccount).filter(
                ChartOfAccount.tenant_id == elis_tenant.id,
                ChartOfAccount.code == code,
                ChartOfAccount.truck_id.is_(None)
            ).first()
            
            if account:
                # Check if account is referenced by any journal entry lines
                line_count = db.query(JournalEntryLine).filter(
                    JournalEntryLine.account_id == account.id
                ).count()
                
                if line_count == 0:
                    if account.is_active:
                        account.is_active = False
                        deactivated_count += 1
                        print(f"   - Deactivated {account.code} ({account.name})")
                else:
                    print(f"   - Skipped {account.code} ({account.name}) - has {line_count} journal entry lines")
        
        if deactivated_count > 0:
            db.commit()
            print(f"   ✓ Deactivated {deactivated_count} unused accounts")
        else:
            print("   ✓ No unused accounts to deactivate")
        
        # Step 4: Ensure journal entries have truck_id = NULL for Elis Logistics
        print("\n4. Ensuring journal entries have truck_id = NULL...")
        entries_with_truck_id = db.query(JournalEntry).filter(
            JournalEntry.tenant_id == elis_tenant.id,
            JournalEntry.truck_id.isnot(None)
        ).all()
        
        if entries_with_truck_id:
            print(f"   Found {len(entries_with_truck_id)} journal entries with truck_id set")
            for entry in entries_with_truck_id:
                entry.truck_id = None
            db.commit()
            print(f"   ✓ Updated {len(entries_with_truck_id)} journal entries")
        else:
            print("   ✓ All journal entries already have truck_id = NULL")
        
        # Step 5: Ensure journal entry lines have truck_id = NULL (they inherit from entries)
        print("\n5. Ensuring journal entry lines have truck_id = NULL...")
        # Get all journal entry IDs for this tenant
        entry_ids = [e.id for e in db.query(JournalEntry.id).filter(
            JournalEntry.tenant_id == elis_tenant.id
        ).all()]
        
        if entry_ids:
            lines_with_truck_id = db.query(JournalEntryLine).filter(
                JournalEntryLine.journal_entry_id.in_(entry_ids),
                JournalEntryLine.truck_id.isnot(None)
            ).all()
            
            if lines_with_truck_id:
                print(f"   Found {len(lines_with_truck_id)} journal entry lines with truck_id set")
                for line in lines_with_truck_id:
                    line.truck_id = None
                db.commit()
                print(f"   ✓ Updated {len(lines_with_truck_id)} journal entry lines")
            else:
                print("   ✓ All journal entry lines already have truck_id = NULL")
        else:
            print("   ✓ No journal entries found for this tenant")
        
        print("\n" + "=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)
        print(f"\nSummary for {elis_tenant.name}:")
        print(f"  - Accounts updated (truck_id = NULL): {len(accounts_with_truck_id) if accounts_with_truck_id else 0}")
        print(f"  - Minimal accounts ensured: {len(minimal_accounts)}")
        print(f"  - Account conflicts resolved: {conflict_resolved}")
        print(f"  - Unused accounts deactivated: {deactivated_count}")
        print(f"  - Journal entries updated (truck_id = NULL): {len(entries_with_truck_id) if entries_with_truck_id else 0}")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 1
    finally:
        db.close()

if __name__ == "__main__":
    exit_code = migrate()
    sys.exit(exit_code)

