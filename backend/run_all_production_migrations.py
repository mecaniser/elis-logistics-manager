#!/usr/bin/env python3
"""
Master script to run all production migrations in order
Works with both SQLite (local) and PostgreSQL (Railway)

Usage:
    python3 backend/run_all_production_migrations.py
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
        
        # Get the migration function (usually named 'migrate')
        if hasattr(module, 'migrate'):
            result = module.migrate()
            if result not in (None, 0):
                print(f"✗ Migration returned non-zero status: {result}")
                return False
        else:
            print(f"✗ No 'migrate' function found in {script_name}")
            return False
        
        print(f"✓ {description} completed successfully")
        return True
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all migrations in order"""
    migrations = [
        ("migrate_add_tenant_support.py", "Add tenant support (tenants table, tenant_id columns)"),
        ("migrate_add_tenant_details.py", "Add tenant business details (EIN, address, etc.)"),
        ("migrate_add_vehicle_type_tag_number.py", "Add vehicle_type and tag_number to trucks"),
        ("migrate_add_suv_vehicle_type.py", "Add 'suv' as vehicle type option"),
        ("migrate_add_vin.py", "Add vin column to trucks"),
        ("migrate_add_investment_fields.py", "Add investment fields (cash_investment, loan_amount, total_cost)"),
        ("migrate_add_registration_fee.py", "Add registration_fee column"),
        ("migrate_add_interest_rate.py", "Add interest_rate column"),
        ("migrate_add_additional_expenses.py", "Add additional_expenses column for custom investment expenses"),
        ("migrate_add_current_loan_balance.py", "Add current_loan_balance column"),
        ("migrate_add_loan_paid_off_date.py", "Add loan_paid_off_date column"),
        ("migrate_create_vehicle_documents.py", "Create vehicle_documents table"),
        ("migrate_recreate_chart_of_accounts_table.py", "Fix chart of accounts unique constraint"),
        ("migrate_add_per_asset_accounting.py", "Add per-asset accounting support (truck_id columns)"),
        ("migrate_add_block_ids.py", "Add block_ids to settlements"),
        ("migrate_add_custom_expense_descriptions.py", "Add custom_expense_descriptions to settlements"),
        ("migrate_add_custom_expense_validation.py", "Add custom_expense_validation to settlements"),
        ("migrate_add_reimbursement_deduction_details.py", "Add reimbursement/deduction details to settlements"),
        ("migrate_add_missing_settlement_columns.py", "Add missing settlement columns"),
        ("migrate_add_settlement_income_split_fields.py", "Add trailer-income split tracking to settlements"),
        ("migrate_add_duplicate_block_ids_warning.py", "Add duplicate_block_ids_warning to settlements"),
        ("migrate_add_repair_title_details.py", "Add title and details to repairs"),
        ("migrate_add_repair_miles.py", "Add miles to repairs"),
        ("migrate_add_invoice_number.py", "Add invoice_number to repairs"),
        ("migrate_add_image_paths.py", "Add image_paths to repairs"),
        ("migrate_add_depreciation_fields.py", "Add depreciation fields to trucks (purchase_date, depreciation_method, cost_basis, etc.)"),
        ("migrate_wave1_correctness.py", "Add journal entry soft-delete and reference uniqueness safeguards"),
        ("migrate_create_accounting_entries.py", "Create accounting entries for existing data"),
        ("migrate_add_tenant_id_to_journal_entry_lines.py", "Add tenant_id to journal_entry_lines for explicit tenant isolation"),
        ("migrate_simplify_elis_logistics_accounts.py", "Simplify chart of accounts for Elis Logistics LLC (remove per-asset complexity)"),
        ("migrate_recalculate_loan_interest_with_principal.py", "Recalculate loan interest chronologically with decreasing balance as principal is paid"),
        ("migrate_recalculate_current_loan_balances.py", "Resync current_loan_balance from full replay history"),
    ]
    
    print("\n" + "="*60)
    print("PRODUCTION MIGRATION SCRIPT")
    print("Running all migrations in order")
    print("="*60)
    
    failed = []
    for script_name, description in migrations:
        success = run_migration(script_name, description)
        if not success:
            failed.append((script_name, description))
            response = input("\n⚠️  Migration failed. Continue with next migration? (y/n): ")
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
        print("\nNext steps:")
        print("1. Verify tenants exist: SELECT * FROM tenants;")
        print("2. For LS Logistics, accounts will be created per truck/trailer automatically")
        print("3. Test the API endpoints to ensure everything works")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
