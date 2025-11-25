#!/usr/bin/env python3
"""
Run settlement-related migrations (custom_expense_validation, reimbursement_details, deduction_details)
Works with both SQLite (local) and PostgreSQL (Railway)
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
        module_name = script_name.replace('.py', '').replace('/', '.')
        module = __import__(module_name, fromlist=[''])
        
        # Get the migration function (usually named after the script)
        func_name = script_name.replace('.py', '').split('/')[-1]
        if hasattr(module, func_name):
            getattr(module, func_name)()
        elif hasattr(module, 'migrate_add_custom_expense_validation'):
            module.migrate_add_custom_expense_validation()
        elif hasattr(module, 'migrate_add_reimbursement_deduction_details'):
            module.migrate_add_reimbursement_deduction_details()
        else:
            # Try to find any function that looks like a migration
            for attr in dir(module):
                if 'migrate' in attr.lower() and callable(getattr(module, attr)):
                    getattr(module, attr)()
                    break
            else:
                print(f"✗ Could not find migration function in {script_name}")
                return False
        
        print(f"✓ {description} completed successfully")
        return True
    except Exception as e:
        print(f"✗ Error running {script_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all settlement-related migrations"""
    print("\n" + "="*60)
    print("SETTLEMENT MIGRATIONS")
    print("="*60)
    print("\nThis script will run the following migrations:")
    print("  1. custom_expense_validation")
    print("  2. reimbursement_details and deduction_details")
    print()
    
    migrations = [
        ("migrate_add_custom_expense_validation.py", "Add custom_expense_validation column"),
        ("migrate_add_reimbursement_deduction_details.py", "Add reimbursement_details and deduction_details columns"),
    ]
    
    success_count = 0
    for script_name, description in migrations:
        if run_migration(script_name, description):
            success_count += 1
    
    print("\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    print(f"✓ Successful: {success_count}/{len(migrations)}")
    if success_count == len(migrations):
        print("\n✓ All migrations completed successfully!")
        return 0
    else:
        print(f"\n✗ {len(migrations) - success_count} migration(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

