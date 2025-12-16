# Production Deployment Migration Guide

This guide covers all migrations needed for production deployment, including the new per-asset accounting feature for LS Logistics.

## Migration Order (Run Sequentially)

### 1. Core Tenant Support
```bash
python3 backend/migrate_add_tenant_support.py
```
- Creates `tenants` table
- Adds `tenant_id` to trucks, chart_of_accounts, journal_entries
- Creates default "Elis Logistics" tenant

### 2. Tenant Details
```bash
python3 backend/migrate_add_tenant_details.py
```
- Adds business detail columns (EIN, address, bank accounts, etc.)

### 3. Vehicle Type & Tag Number
```bash
python3 backend/migrate_add_vehicle_type_tag_number.py
```
- Adds `vehicle_type` and `tag_number` columns to trucks table

### 4. Investment Fields
```bash
python3 backend/migrate_add_investment_fields.py
```
- Adds `cash_investment`, `loan_amount`, `total_cost` columns

### 5. Registration Fee
```bash
python3 backend/migrate_add_registration_fee.py
```
- Adds `registration_fee` column

### 6. Interest Rate
```bash
python3 backend/migrate_add_interest_rate.py
```
- Adds `interest_rate` column

### 7. Current Loan Balance
```bash
python3 backend/migrate_add_current_loan_balance.py
```
- Adds `current_loan_balance` column

### 8. Chart of Accounts Constraint Fix
```bash
python3 backend/migrate_recreate_chart_of_accounts_table.py
```
- Updates unique constraint from `UNIQUE (code)` to `UNIQUE (tenant_id, code)`

### 9. **Per-Asset Accounting (NEW)**
```bash
python3 backend/migrate_add_per_asset_accounting.py
```
- Adds `truck_id` to `chart_of_accounts` and `journal_entries`
- Updates unique constraint to `UNIQUE (tenant_id, code, truck_id)`
- Creates indexes on `truck_id` columns

### 10. Settlement Columns
```bash
python3 backend/migrate_add_block_ids.py
python3 backend/migrate_add_custom_expense_descriptions.py
python3 backend/migrate_add_custom_expense_validation.py
python3 backend/migrate_add_reimbursement_deduction_details.py
python3 backend/migrate_add_missing_settlement_columns.py
python3 backend/migrate_add_duplicate_block_ids_warning.py
```
- Adds various settlement-related columns

### 11. Repair Columns
```bash
python3 backend/migrate_add_repair_title_details.py
python3 backend/migrate_add_repair_miles.py
python3 backend/migrate_add_invoice_number.py
python3 backend/migrate_add_image_paths.py
```
- Adds repair-related columns

### 12. Create Accounting Entries
```bash
python3 backend/migrate_create_accounting_entries.py
```
- Creates standard chart of accounts for each tenant
- Creates journal entries for existing settlements and repairs

## Railway Production Deployment

### Option 1: Railway CLI (Recommended)
```bash
# Run migrations in order
railway run python3 backend/migrate_add_tenant_support.py
railway run python3 backend/migrate_add_tenant_details.py
railway run python3 backend/migrate_add_vehicle_type_tag_number.py
railway run python3 backend/migrate_add_investment_fields.py
railway run python3 backend/migrate_add_registration_fee.py
railway run python3 backend/migrate_add_interest_rate.py
railway run python3 backend/migrate_add_current_loan_balance.py
railway run python3 backend/migrate_recreate_chart_of_accounts_table.py
railway run python3 backend/migrate_add_per_asset_accounting.py
railway run python3 backend/migrate_add_block_ids.py
railway run python3 backend/migrate_add_custom_expense_descriptions.py
railway run python3 backend/migrate_add_custom_expense_validation.py
railway run python3 backend/migrate_add_reimbursement_deduction_details.py
railway run python3 backend/migrate_add_missing_settlement_columns.py
railway run python3 backend/migrate_add_duplicate_block_ids_warning.py
railway run python3 backend/migrate_add_repair_title_details.py
railway run python3 backend/migrate_add_repair_miles.py
railway run python3 backend/migrate_add_invoice_number.py
railway run python3 backend/migrate_add_image_paths.py
railway run python3 backend/migrate_create_accounting_entries.py
```

### Option 2: SSH into Railway Container
```bash
railway shell
cd /app/backend
PYTHONPATH=/app/backend python3 migrate_add_tenant_support.py
PYTHONPATH=/app/backend python3 migrate_add_tenant_details.py
# ... continue with all migrations in order
```

### Option 3: Automated Script
Create a script that runs all migrations in order (see below).

## Verification After Migration

```sql
-- Check tenants exist
SELECT id, name, business_type FROM tenants;

-- Verify truck_id columns exist
SELECT sql FROM sqlite_master WHERE type='table' AND name='chart_of_accounts';
-- Should show: UNIQUE (tenant_id, code, truck_id)

SELECT sql FROM sqlite_master WHERE type='table' AND name='journal_entries';
-- Should show truck_id column

-- Check all data has tenant_id
SELECT COUNT(*) FROM trucks WHERE tenant_id IS NULL;  -- Should be 0
SELECT COUNT(*) FROM chart_of_accounts WHERE tenant_id IS NULL;  -- Should be 0
SELECT COUNT(*) FROM journal_entries WHERE tenant_id IS NULL;  -- Should be 0
```

## Important Notes

1. **All migrations are idempotent** - safe to run multiple times
2. **Backup your database** before running migrations in production
3. **Run migrations in order** - some depend on previous ones
4. **For LS Logistics**: After migrations, accounts will be created per truck/trailer automatically when settlements/repairs are created
5. **Database name**: The default is `elisgroup.db` (SQLite) or use `DATABASE_URL` env var for PostgreSQL

## Troubleshooting

- If a migration fails, check the error message and fix the issue before continuing
- The `migrate_recreate_chart_of_accounts_table.py` and `migrate_add_per_asset_accounting.py` scripts create backup tables automatically
- For PostgreSQL, some migrations may need slight adjustments (SQLite-specific syntax)

