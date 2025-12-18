"""
Migration script to recreate chart_of_accounts table with correct unique constraint
SQLite doesn't support ALTER TABLE to modify constraints, so we recreate the table
PostgreSQL can use ALTER TABLE to modify constraints
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, DATABASE_URL

def migrate():
    """Recreate chart_of_accounts table with correct unique constraint"""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("RECREATING CHART OF ACCOUNTS TABLE")
        print("=" * 80)

        is_sqlite = DATABASE_URL.startswith("sqlite")

        with engine.connect() as connection:
            if is_sqlite:
                # SQLite: Check if table exists
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
                table_row = result.fetchone()
                if not table_row or not table_row[0]:
                    print("Could not read table definition")
                    return
                    
                table_sql = table_row[0]
                print(f"\nCurrent table definition includes: UNIQUE (code)")
                
                # Check if constraint includes tenant_id, code, and truck_id
                table_sql_normalized = table_sql.replace(" ", "").lower()
                if ("unique(tenant_id,code,truck_id)" in table_sql_normalized or 
                    "unique(tenant_id,code,truck_id)" in table_sql_normalized):
                    print("✓ Table already has correct constraint (tenant_id, code, truck_id)")
                    return
                elif "unique(tenant_id,code)" in table_sql_normalized:
                    print("⚠ Table has old constraint (tenant_id, code) - needs update to include truck_id")
                    # Continue to recreate table
                else:
                    print("⚠ Table has old constraint - needs update")

                # Check if truck_id column exists
                result = connection.execute(text("PRAGMA table_info(chart_of_accounts)"))
                columns = [row[1] for row in result.fetchall()]
                has_truck_id = 'truck_id' in columns
                
                # Backup data
                print("\n1. Backing up existing data...")
                if has_truck_id:
                    connection.execute(text("""
                        CREATE TABLE chart_of_accounts_backup AS 
                        SELECT * FROM chart_of_accounts
                    """))
                else:
                    # If truck_id doesn't exist, add it as NULL
                    connection.execute(text("""
                        CREATE TABLE chart_of_accounts_backup AS 
                        SELECT id, tenant_id, code, name, account_type, parent_id, is_active, created_at, NULL as truck_id
                        FROM chart_of_accounts
                    """))
                connection.commit()
                result = connection.execute(text("SELECT COUNT(*) FROM chart_of_accounts_backup"))
                backup_count = result.fetchone()[0]
                print(f"   ✓ Backed up {backup_count} records")

                # Check for duplicates that would violate new constraint
                print("\n1a. Checking for duplicate accounts...")
                if has_truck_id:
                    duplicate_check = text("""
                        SELECT tenant_id, code, truck_id, COUNT(*) as cnt
                        FROM chart_of_accounts_backup
                        GROUP BY tenant_id, code, truck_id
                        HAVING COUNT(*) > 1
                    """)
                else:
                    duplicate_check = text("""
                        SELECT tenant_id, code, COUNT(*) as cnt
                        FROM chart_of_accounts_backup
                        GROUP BY tenant_id, code
                        HAVING COUNT(*) > 1
                    """)
                duplicates = connection.execute(duplicate_check).fetchall()
                if duplicates:
                    print(f"   ⚠ Found {len(duplicates)} duplicate account groups")
                    print("   Removing duplicates (keeping first occurrence)...")
                    if has_truck_id:
                        # Delete duplicates, keeping the one with the lowest id
                        connection.execute(text("""
                            DELETE FROM chart_of_accounts_backup
                            WHERE id NOT IN (
                                SELECT MIN(id)
                                FROM chart_of_accounts_backup
                                GROUP BY tenant_id, code, truck_id
                            )
                        """))
                    else:
                        connection.execute(text("""
                            DELETE FROM chart_of_accounts_backup
                            WHERE id NOT IN (
                                SELECT MIN(id)
                                FROM chart_of_accounts_backup
                                GROUP BY tenant_id, code
                            )
                        """))
                    connection.commit()
                    result = connection.execute(text("SELECT COUNT(*) FROM chart_of_accounts_backup"))
                    deduped_count = result.fetchone()[0]
                    print(f"   ✓ Deduplicated: {backup_count} -> {deduped_count} records")

                # Drop old table
                print("\n2. Dropping old table...")
                connection.execute(text("DROP TABLE chart_of_accounts"))
                connection.commit()
                print("   ✓ Dropped old table")

                # Create new table with correct constraint (tenant_id, code, truck_id)
                print("\n3. Creating new table with correct constraint...")
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
                print("   ✓ Created new table with constraint (tenant_id, code, truck_id)")

                # Create indexes
                print("\n4. Creating indexes...")
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_chart_of_accounts_tenant_id ON chart_of_accounts (tenant_id)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS idx_tenant_account_type_active ON chart_of_accounts (tenant_id, account_type, is_active)"))
                connection.commit()
                print("   ✓ Created indexes")

                # Restore data
                print("\n5. Restoring data...")
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
                print("\n6. Cleaning up backup table...")
                connection.execute(text("DROP TABLE chart_of_accounts_backup"))
                connection.commit()
                print("   ✓ Cleaned up")
            else:
                # PostgreSQL: Use ALTER TABLE to modify constraints
                # Check if table exists
                result = connection.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_name = 'chart_of_accounts'
                """))
                if not result.fetchone():
                    print("Table chart_of_accounts does not exist. Creating it...")
                    from app.models.chart_of_accounts import ChartOfAccount
                    ChartOfAccount.__table__.create(engine)
                    print("✓ Table created")
                    return

                # Check if truck_id column exists
                result = connection.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'chart_of_accounts' 
                    AND column_name = 'truck_id'
                """))
                has_truck_id = result.fetchone() is not None
                
                if not has_truck_id:
                    print("Adding truck_id column...")
                    connection.execute(text("ALTER TABLE chart_of_accounts ADD COLUMN truck_id INTEGER"))
                    connection.execute(text("ALTER TABLE chart_of_accounts ADD CONSTRAINT fk_truck FOREIGN KEY (truck_id) REFERENCES trucks(id)"))
                    connection.commit()
                    print("   ✓ Added truck_id column")

                # Check current constraint
                result = connection.execute(text("""
                    SELECT tc.constraint_name,
                           string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_name = 'chart_of_accounts'
                    AND tc.constraint_type = 'UNIQUE'
                    AND tc.constraint_name LIKE '%tenant_id%code%'
                    GROUP BY tc.constraint_name
                """))
                constraint = result.fetchone()
                
                if constraint and constraint[1] and 'tenant_id' in constraint[1] and 'code' in constraint[1] and 'truck_id' in constraint[1]:
                    print("✓ Table already has correct constraint (tenant_id, code, truck_id)")
                    return

                # Drop old constraint if it exists
                result = connection.execute(text("""
                    SELECT constraint_name 
                    FROM information_schema.table_constraints 
                    WHERE table_name = 'chart_of_accounts' 
                    AND constraint_type = 'UNIQUE'
                    AND (constraint_name LIKE '%code%' OR constraint_name LIKE '%tenant%')
                """))
                old_constraints = result.fetchall()
                for old_constraint in old_constraints:
                    print(f"   Dropping old constraint: {old_constraint[0]}")
                    connection.execute(text(f"ALTER TABLE chart_of_accounts DROP CONSTRAINT IF EXISTS {old_constraint[0]}"))
                    connection.commit()

                # Add new constraint (tenant_id, code, truck_id)
                print("\n1. Adding new unique constraint (tenant_id, code, truck_id)...")
                connection.execute(text("""
                    ALTER TABLE chart_of_accounts 
                    ADD CONSTRAINT unique_code_per_tenant_truck 
                    UNIQUE (tenant_id, code, truck_id)
                """))
                connection.commit()
                print("   ✓ Added new unique constraint")

                # Ensure indexes exist
                print("\n2. Ensuring indexes exist...")
                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_chart_of_accounts_tenant_id 
                    ON chart_of_accounts (tenant_id)
                """))
                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_tenant_account_type_active 
                    ON chart_of_accounts (tenant_id, account_type, is_active)
                """))
                connection.commit()
                print("   ✓ Indexes created")

        print("\n" + "=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        # Try to restore from backup if it exists (SQLite only)
        if DATABASE_URL.startswith("sqlite"):
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

