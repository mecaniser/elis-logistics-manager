#!/usr/bin/env python3
"""
Seed script: Create test tenant "Elis Logistics LLC" and test journal entry
"""
import sys
import os
from datetime import date

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.tenant import Tenant
from app.models.journal_entry import JournalEntry
from app.models.journal_entry_line import JournalEntryLine
from app.models.chart_of_accounts import ChartOfAccount
from app.services.accounting_service_minimal import initialize_minimal_logistics_accounts

def seed():
    """Create test tenant and journal entry"""
    db: Session = SessionLocal()
    
    try:
        # 1. Create or get tenant "Elis Logistics LLC"
        tenant = db.query(Tenant).filter(Tenant.name == "Elis Logistics LLC").first()
        if not tenant:
            print("Creating tenant 'Elis Logistics LLC'...")
            tenant = Tenant(
                name="Elis Logistics LLC",
                business_type="logistics",
                is_active=True
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"✓ Created tenant: {tenant.name} (ID: {tenant.id})")
        else:
            print(f"✓ Tenant already exists: {tenant.name} (ID: {tenant.id})")
        
        # 2. Initialize chart of accounts
        print("\nInitializing chart of accounts...")
        try:
            accounts = initialize_minimal_logistics_accounts(db, tenant.id)
            print(f"✓ Initialized {len(accounts)} accounts")
        except ValueError as e:
            if "already initialized" in str(e).lower():
                print(f"✓ Chart of accounts already initialized")
                accounts = db.query(ChartOfAccount).filter(ChartOfAccount.tenant_id == tenant.id).all()
            else:
                raise
        
        # 3. Get Cash (1000) and Settlement Income (4000) accounts
        cash_account = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant.id,
            ChartOfAccount.code == "1000"
        ).first()
        
        settlement_income_account = db.query(ChartOfAccount).filter(
            ChartOfAccount.tenant_id == tenant.id,
            ChartOfAccount.code == "4000"
        ).first()
        
        if not cash_account or not settlement_income_account:
            raise ValueError("Required accounts not found. Cash (1000) or Settlement Income (4000) missing.")
        
        # 4. Check if test entry already exists
        existing_entry = db.query(JournalEntry).filter(
            JournalEntry.tenant_id == tenant.id,
            JournalEntry.description == "Seed test settlement"
        ).first()
        
        if existing_entry:
            print(f"✓ Test journal entry already exists (ID: {existing_entry.id})")
            return
        
        # 5. Create test journal entry
        print("\nCreating test journal entry...")
        journal_entry = JournalEntry(
            tenant_id=tenant.id,
            entry_date=date.today(),
            reference_type="manual",
            description="Seed test settlement"
        )
        db.add(journal_entry)
        db.flush()  # Get the ID
        
        # 6. Create journal entry lines
        # Debit Cash (1000) = 1000
        # Credit Settlement Income (4000) = 1000
        lines = [
            JournalEntryLine(
                tenant_id=tenant.id,
                journal_entry_id=journal_entry.id,
                account_id=cash_account.id,
                debit=1000.00,
                credit=0.00,
                description="Cash received"
            ),
            JournalEntryLine(
                tenant_id=tenant.id,
                journal_entry_id=journal_entry.id,
                account_id=settlement_income_account.id,
                debit=0.00,
                credit=1000.00,
                description="Settlement income"
            )
        ]
        
        for line in lines:
            db.add(line)
        
        db.commit()
        db.refresh(journal_entry)
        
        print(f"✓ Created test journal entry (ID: {journal_entry.id})")
        print(f"  - Debit Cash (1000): $1,000.00")
        print(f"  - Credit Settlement Income (4000): $1,000.00")
        print("\n✓ Seed completed successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Seed failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()

