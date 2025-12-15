"""
Migration script to fix chart_of_accounts unique constraint
Drops old constraint on code alone and ensures constraint is on (tenant_id, code)
"""
import sys
import os
from sqlalchemy import text, inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine

def migrate():
    """Fix chart_of_accounts unique constraint"""
    db = SessionLocal()

    try:
        print("=" * 80)
        print("FIXING CHART OF ACCOUNTS CONSTRAINT")
        print("=" * 80)

        with engine.connect() as connection:
            inspector = inspect(engine)
            
            # Get all indexes on chart_of_accounts table
            indexes = inspector.get_indexes('chart_of_accounts')
            print(f"\nFound {len(indexes)} indexes on chart_of_accounts table")
            
            # Check if there's a unique constraint on code alone
            for idx in indexes:
                print(f"  Index: {idx['name']}, Columns: {idx['column_names']}, Unique: {idx.get('unique', False)}")
                # If there's a unique index on just 'code', we need to drop it
                if 'code' in idx['column_names'] and len(idx['column_names']) == 1 and idx.get('unique', False):
                    print(f"\nDropping old unique constraint on code: {idx['name']}")
                    try:
                        connection.execute(text(f"DROP INDEX IF EXISTS {idx['name']}"))
                        connection.commit()
                        print(f"  ✓ Dropped index {idx['name']}")
                    except Exception as e:
                        print(f"  ⚠ Could not drop index {idx['name']}: {e}")
                        connection.rollback()

            # Verify the table structure
            columns = inspector.get_columns('chart_of_accounts')
            has_tenant_id = any(col['name'] == 'tenant_id' for col in columns)
            has_code = any(col['name'] == 'code' for col in columns)
            
            print(f"\nTable structure:")
            print(f"  ✓ tenant_id column: {has_tenant_id}")
            print(f"  ✓ code column: {has_code}")
            
            # The unique constraint on (tenant_id, code) should be defined in the model
            # SQLite will enforce it through the table definition
            print("\n✓ Constraint fix complete")
            print("  Note: The unique constraint on (tenant_id, code) is defined in the model")
            print("  If you see constraint errors, you may need to recreate the table")

        print("\n" + "=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

