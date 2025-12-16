"""
Migration script to add per-asset accounting support for LS Logistics
Adds truck_id columns to chart_of_accounts and journal_entries tables
Updates unique constraint on chart_of_accounts to include truck_id
"""
import sys
import os
from sqlalchemy import text, inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine

def migrate():
    """Add truck_id columns and update constraints for per-asset accounting"""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("ADDING PER-ASSET ACCOUNTING SUPPORT")
        print("=" * 80)

        inspector = inspect(engine)
        
        # Add truck_id to chart_of_accounts if missing
        if 'chart_of_accounts' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('chart_of_accounts')]
            if 'truck_id' not in columns:
                print("\n1. Adding truck_id column to chart_of_accounts table...")
                db.execute(text("ALTER TABLE chart_of_accounts ADD COLUMN truck_id INTEGER"))
                db.commit()
                print("   ✓ Added truck_id column")
                
                # Create index
                print("   Creating index on truck_id...")
                db.execute(text("CREATE INDEX IF NOT EXISTS ix_chart_of_accounts_truck_id ON chart_of_accounts (truck_id)"))
                db.commit()
                print("   ✓ Created index")
            else:
                print("✓ truck_id column already exists in chart_of_accounts")
        
        # Add truck_id to journal_entries if missing
        if 'journal_entries' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('journal_entries')]
            if 'truck_id' not in columns:
                print("\n2. Adding truck_id column to journal_entries table...")
                db.execute(text("ALTER TABLE journal_entries ADD COLUMN truck_id INTEGER"))
                db.commit()
                print("   ✓ Added truck_id column")
                
                # Create index
                print("   Creating index on truck_id...")
                db.execute(text("CREATE INDEX IF NOT EXISTS ix_journal_entries_truck_id ON journal_entries (truck_id)"))
                db.commit()
                print("   ✓ Created index")
            else:
                print("✓ truck_id column already exists in journal_entries")
        
        # Update unique constraint on chart_of_accounts
        # SQLite doesn't support ALTER TABLE to modify constraints, so we need to recreate
        print("\n3. Checking unique constraint on chart_of_accounts...")
        with engine.connect() as connection:
            result = connection.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='chart_of_accounts'"))
            table_row = result.fetchone()
            if table_row:
                table_sql = table_row[0]
                # Check if constraint already includes truck_id
                if "UNIQUE (tenant_id, code, truck_id)" in table_sql or "UNIQUE(tenant_id,code,truck_id)" in table_sql.replace(" ", ""):
                    print("   ✓ Unique constraint already includes truck_id")
                else:
                    print("   Recreating table with updated unique constraint...")
                    
                    # Backup data
                    print("   Backing up existing data...")
                    connection.execute(text("""
                        CREATE TABLE chart_of_accounts_backup AS 
                        SELECT * FROM chart_of_accounts
                    """))
                    connection.commit()
                    result = connection.execute(text("SELECT COUNT(*) FROM chart_of_accounts_backup"))
                    backup_count = result.fetchone()[0]
                    print(f"   ✓ Backed up {backup_count} records")
                    
                    # Drop old table
                    print("   Dropping old table...")
                    connection.execute(text("DROP TABLE chart_of_accounts"))
                    connection.commit()
                    print("   ✓ Dropped old table")
                    
                    # Create new table with updated constraint
                    print("   Creating new table with updated constraint...")
                    connection.execute(text("""
                        CREATE TABLE chart_of_accounts (
                            id INTEGER NOT NULL PRIMARY KEY,
                            tenant_id INTEGER NOT NULL,
                            truck_id INTEGER,
                            code VARCHAR(20) NOT NULL,
                            name VARCHAR(200) NOT NULL,
                            account_type VARCHAR(20) NOT NULL,
                            parent_id INTEGER,
                            is_active BOOLEAN NOT NULL DEFAULT 1,
                            created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                            FOREIGN KEY(parent_id) REFERENCES chart_of_accounts (id),
                            FOREIGN KEY(tenant_id) REFERENCES tenants (id),
                            FOREIGN KEY(truck_id) REFERENCES trucks (id),
                            UNIQUE (tenant_id, code, truck_id)
                        )
                    """))
                    connection.commit()
                    print("   ✓ Created new table")
                    
                    # Create indexes
                    print("   Creating indexes...")
                    connection.execute(text("CREATE INDEX ix_chart_of_accounts_tenant_id ON chart_of_accounts (tenant_id)"))
                    connection.execute(text("CREATE INDEX ix_chart_of_accounts_truck_id ON chart_of_accounts (truck_id)"))
                    connection.commit()
                    print("   ✓ Created indexes")
                    
                    # Restore data
                    print("   Restoring data...")
                    connection.execute(text("""
                        INSERT INTO chart_of_accounts 
                        (id, tenant_id, truck_id, code, name, account_type, parent_id, is_active, created_at)
                        SELECT id, tenant_id, truck_id, code, name, account_type, parent_id, is_active, created_at
                        FROM chart_of_accounts_backup
                    """))
                    connection.commit()
                    result = connection.execute(text("SELECT COUNT(*) FROM chart_of_accounts"))
                    restored_count = result.fetchone()[0]
                    print(f"   ✓ Restored {restored_count} records")
                    
                    # Drop backup table
                    print("   Cleaning up backup table...")
                    connection.execute(text("DROP TABLE chart_of_accounts_backup"))
                    connection.commit()
                    print("   ✓ Cleaned up")
        
        print("\n" + "=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)
        print("\nNext steps:")
        print("1. For LS Logistics tenant, accounts will be created per truck/trailer")
        print("2. Run ensure_standard_accounts_exist for LS Logistics to create per-asset accounts")

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        # Try to restore from backup if it exists
        try:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='chart_of_accounts_backup'"))
                if result.fetchone():
                    print("\nAttempting to restore from backup...")
                    connection.execute(text("DROP TABLE IF EXISTS chart_of_accounts"))
                    connection.execute(text("ALTER TABLE chart_of_accounts_backup RENAME TO chart_of_accounts"))
                    connection.commit()
                    print("✓ Restored from backup")
        except:
            pass
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

