"""
Migration script to recreate chart_of_accounts table with correct unique constraint
SQLite doesn't support ALTER TABLE to modify constraints, so we recreate the table
"""
import sys
import os
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine

def migrate():
    """Recreate chart_of_accounts table with correct unique constraint"""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("RECREATING CHART OF ACCOUNTS TABLE")
        print("=" * 80)

        with engine.connect() as connection:
            # Check if table exists
            result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='chart_of_accounts'"))
            if not result.fetchone():
                print("Table chart_of_accounts does not exist. Creating it...")
                # Table will be created by SQLAlchemy models
                from app.models.chart_of_accounts import ChartOfAccount
                ChartOfAccount.__table__.create(engine)
                print("✓ Table created")
                return

            # Check current constraint
            result = connection.execute(text("SELECT sql FROM sqlite_master WHERE type='table' AND name='chart_of_accounts'"))
            table_sql = result.fetchone()[0]
            print(f"\nCurrent table definition includes: UNIQUE (code)")
            
            if "UNIQUE (tenant_id, code)" in table_sql or "UNIQUE(tenant_id,code)" in table_sql.replace(" ", ""):
                print("✓ Table already has correct constraint")
                return

            # Backup data
            print("\n1. Backing up existing data...")
            connection.execute(text("""
                CREATE TABLE chart_of_accounts_backup AS 
                SELECT * FROM chart_of_accounts
            """))
            connection.commit()
            result = connection.execute(text("SELECT COUNT(*) FROM chart_of_accounts_backup"))
            backup_count = result.fetchone()[0]
            print(f"   ✓ Backed up {backup_count} records")

            # Drop old table
            print("\n2. Dropping old table...")
            connection.execute(text("DROP TABLE chart_of_accounts"))
            connection.commit()
            print("   ✓ Dropped old table")

            # Create new table with correct constraint
            print("\n3. Creating new table with correct constraint...")
            connection.execute(text("""
                CREATE TABLE chart_of_accounts (
                    id INTEGER NOT NULL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL,
                    code VARCHAR(20) NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    account_type VARCHAR(20) NOT NULL,
                    parent_id INTEGER,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP),
                    FOREIGN KEY(parent_id) REFERENCES chart_of_accounts (id),
                    FOREIGN KEY(tenant_id) REFERENCES tenants (id),
                    UNIQUE (tenant_id, code)
                )
            """))
            connection.commit()
            print("   ✓ Created new table")

            # Create indexes
            print("\n4. Creating indexes...")
            connection.execute(text("CREATE INDEX ix_chart_of_accounts_tenant_id ON chart_of_accounts (tenant_id)"))
            connection.commit()
            print("   ✓ Created indexes")

            # Restore data
            print("\n5. Restoring data...")
            connection.execute(text("""
                INSERT INTO chart_of_accounts 
                (id, tenant_id, code, name, account_type, parent_id, is_active, created_at)
                SELECT id, tenant_id, code, name, account_type, parent_id, is_active, created_at
                FROM chart_of_accounts_backup
            """))
            connection.commit()
            result = connection.execute(text("SELECT COUNT(*) FROM chart_of_accounts"))
            restored_count = result.fetchone()[0]
            print(f"   ✓ Restored {restored_count} records")

            # Drop backup table
            print("\n6. Cleaning up backup table...")
            connection.execute(text("DROP TABLE chart_of_accounts_backup"))
            connection.commit()
            print("   ✓ Cleaned up")

        print("\n" + "=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)

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

