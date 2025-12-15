"""
Migration script to add multi-tenant support
Creates a default tenant and assigns all existing data to it
"""
from app.database import SessionLocal, engine, Base
from app.models.tenant import Tenant
from app.models.truck import Truck
from app.models.chart_of_accounts import ChartOfAccount
from app.models.journal_entry import JournalEntry
from sqlalchemy import text, inspect

def migrate():
    """Add tenant support to existing database"""
    db = SessionLocal()
    
    try:
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine)
        
        # Check and add missing columns to tables
        inspector = inspect(engine)
        
        # Add business_type to tenants if missing
        if 'tenants' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('tenants')]
            if 'business_type' not in columns:
                print("Adding business_type column to tenants table...")
                db.execute(text("ALTER TABLE tenants ADD COLUMN business_type VARCHAR(50) DEFAULT 'logistics'"))
                db.commit()
                print("✓ Added business_type column to tenants")
        
        # Add tenant_id to trucks if missing
        if 'trucks' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('trucks')]
            if 'tenant_id' not in columns:
                print("Adding tenant_id column to trucks table...")
                db.execute(text("ALTER TABLE trucks ADD COLUMN tenant_id INTEGER"))
                db.commit()
                print("✓ Added tenant_id column to trucks")
        
        # Add tenant_id to chart_of_accounts if missing
        if 'chart_of_accounts' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('chart_of_accounts')]
            if 'tenant_id' not in columns:
                print("Adding tenant_id column to chart_of_accounts table...")
                db.execute(text("ALTER TABLE chart_of_accounts ADD COLUMN tenant_id INTEGER"))
                db.commit()
                print("✓ Added tenant_id column to chart_of_accounts")
        
        # Add tenant_id to journal_entries if missing
        if 'journal_entries' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('journal_entries')]
            if 'tenant_id' not in columns:
                print("Adding tenant_id column to journal_entries table...")
                db.execute(text("ALTER TABLE journal_entries ADD COLUMN tenant_id INTEGER"))
                db.commit()
                print("✓ Added tenant_id column to journal_entries")
        
        # Create default tenant if it doesn't exist (Elis Logistics)
        default_tenant = db.query(Tenant).filter(Tenant.name == "Elis Logistics").first()
        if not default_tenant:
            default_tenant = Tenant(name="Elis Logistics", business_type="logistics", is_active=True)
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
            print(f"✓ Created default tenant: {default_tenant.name} (ID: {default_tenant.id}, Type: {default_tenant.business_type})")
        else:
            # Update business_type if missing (handle case where column was just added)
            db.refresh(default_tenant)
            if not default_tenant.business_type:
                default_tenant.business_type = "logistics"
                db.commit()
                print(f"✓ Updated tenant business_type to 'logistics'")
            print(f"✓ Default tenant already exists: {default_tenant.name} (ID: {default_tenant.id}, Type: {default_tenant.business_type})")
        
        tenant_id = default_tenant.id
        
        # Update all trucks to belong to default tenant
        trucks_without_tenant = db.query(Truck).filter(Truck.tenant_id.is_(None)).all()
        if trucks_without_tenant:
            for truck in trucks_without_tenant:
                truck.tenant_id = tenant_id
            db.commit()
            print(f"✓ Updated {len(trucks_without_tenant)} trucks to tenant {tenant_id}")
        else:
            print("✓ All trucks already have tenant_id")
        
        # Update all chart of accounts to belong to default tenant
        accounts_without_tenant = db.query(ChartOfAccount).filter(ChartOfAccount.tenant_id.is_(None)).all()
        if accounts_without_tenant:
            for account in accounts_without_tenant:
                account.tenant_id = tenant_id
            db.commit()
            print(f"✓ Updated {len(accounts_without_tenant)} chart of accounts to tenant {tenant_id}")
        else:
            print("✓ All chart of accounts already have tenant_id")
        
        # Update all journal entries to belong to default tenant
        entries_without_tenant = db.query(JournalEntry).filter(JournalEntry.tenant_id.is_(None)).all()
        if entries_without_tenant:
            for entry in entries_without_tenant:
                entry.tenant_id = tenant_id
            db.commit()
            print(f"✓ Updated {len(entries_without_tenant)} journal entries to tenant {tenant_id}")
        else:
            print("✓ All journal entries already have tenant_id")
        
        print("\n✓ Migration completed successfully!")
        print(f"  Default tenant ID: {tenant_id}")
        print("  All existing data has been assigned to the default tenant.")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Migration failed: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

