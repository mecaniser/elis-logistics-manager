#!/usr/bin/env python3
"""
Master migration script to run all loan interest related migrations in order
Works with both SQLite (local) and PostgreSQL (Railway)

Run this script on production to ensure all database columns are added before
recalculating loan interest.
"""
import sys
import os

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

def run_migration(script_name, description):
    """Run a migration script"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Script: {script_name}")
    print(f"{'='*60}\n")
    
    script_path = os.path.join(backend_dir, script_name)
    
    if not os.path.exists(script_path):
        print(f"✗ Script not found: {script_path}")
        return False
    
    try:
        # Import and run the migration function
        module_name = script_name.replace('.py', '')
        module = __import__(module_name, fromlist=[''])
        
        # Get the main migration function (usually named after the script)
        func_name = module_name.replace('migrate_', '').replace('_', ' ')
        func_name = ''.join(word.capitalize() for word in func_name.split())
        func_name = func_name.replace(' ', '_')
        func_name = 'migrate_' + func_name.lower().replace(' ', '_')
        
        # Try common function names
        migration_func = None
        for name in [func_name, 'migrate', 'migrate_add_investment_fields', 
                     'migrate_add_registration_fee', 'migrate_add_interest_rate',
                     'migrate_add_current_loan_balance', 'migrate_recalculate_loan_interest']:
            if hasattr(module, name):
                migration_func = getattr(module, name)
                break
        
        if not migration_func:
            # Try to find any function that starts with 'migrate'
            for attr_name in dir(module):
                if attr_name.startswith('migrate') and callable(getattr(module, attr_name)):
                    migration_func = getattr(module, attr_name)
                    break
        
        if migration_func:
            migration_func()
            print(f"✓ {description} completed successfully")
            return True
        else:
            print(f"✗ Could not find migration function in {script_name}")
            return False
            
    except Exception as e:
        print(f"✗ Error running {script_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all migrations in order"""
    migrations = [
        ("migrate_add_investment_fields.py", "Add investment fields (cash_investment, loan_amount, total_cost)"),
        ("migrate_add_registration_fee.py", "Add registration_fee column"),
        ("migrate_add_interest_rate.py", "Add interest_rate column"),
        ("migrate_add_current_loan_balance.py", "Add current_loan_balance column"),
        ("migrate_recalculate_loan_interest_with_principal.py", "Recalculate loan interest with principal payments"),
    ]
    
    print("\n" + "="*60)
    print("MASTER MIGRATION SCRIPT")
    print("Running all loan interest migrations in order")
    print("="*60)
    
    failed = []
    for script_name, description in migrations:
        success = run_migration(script_name, description)
        if not success:
            failed.append((script_name, description))
            print(f"\n⚠️  Migration failed: {description}")
            response = input("Continue with next migration? (y/n): ")
            if response.lower() != 'y':
                print("\n✗ Migration aborted by user")
                return False
    
    if failed:
        print(f"\n⚠️  {len(failed)} migration(s) failed:")
        for script_name, description in failed:
            print(f"  - {description} ({script_name})")
        return False
    else:
        print("\n" + "="*60)
        print("✓ ALL MIGRATIONS COMPLETED SUCCESSFULLY")
        print("="*60)
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

