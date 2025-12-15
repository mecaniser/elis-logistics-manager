# Production Migration Guide

This guide outlines the steps needed to migrate production databases for the multi-tenant and accounting features.

## Migration Scripts (Run in Order)

Run these scripts in sequence on your production database:

### 1. Add Tenant Support
```bash
cd backend
PYTHONPATH=/path/to/backend python3 migrate_add_tenant_support.py
```
This script:
- Creates the `tenants` table if it doesn't exist
- Adds `business_type` column to tenants table
- Adds `tenant_id` columns to `trucks`, `chart_of_accounts`, and `journal_entries` tables
- Creates a default "Elis Logistics" tenant
- Assigns all existing data to the default tenant

### 2. Add Tenant Details Columns
```bash
PYTHONPATH=/path/to/backend python3 migrate_add_tenant_details.py
```
This script adds business detail columns to the `tenants` table:
- `ein` (EIN)
- `legal_name`
- `address`, `city`, `state`, `zip_code`
- `phone`, `email`
- `bank_accounts` (JSON)
- `notes`

### 3. Fix Chart of Accounts Constraint
```bash
PYTHONPATH=/path/to/backend python3 migrate_recreate_chart_of_accounts_table.py
```
**IMPORTANT**: This script recreates the `chart_of_accounts` table to fix the unique constraint from `UNIQUE (code)` to `UNIQUE (tenant_id, code)`. It:
- Backs up existing data
- Drops the old table
- Creates a new table with the correct constraint
- Restores all data

### 4. Create Accounting Entries
```bash
PYTHONPATH=/path/to/backend python3 migrate_create_accounting_entries.py
```
This script:
- Ensures standard chart of accounts exist for each tenant
- Creates journal entries for existing settlements and repairs
- Processes all active tenants

## Railway Production Deployment

For Railway deployments, you can run migrations via Railway CLI or SSH:

### Option 1: Railway CLI
```bash
railway run python3 backend/migrate_add_tenant_support.py
railway run python3 backend/migrate_add_tenant_details.py
railway run python3 backend/migrate_recreate_chart_of_accounts_table.py
railway run python3 backend/migrate_create_accounting_entries.py
```

### Option 2: SSH into Railway Container
```bash
railway shell
cd backend
PYTHONPATH=/app/backend python3 migrate_add_tenant_support.py
PYTHONPATH=/app/backend python3 migrate_add_tenant_details.py
PYTHONPATH=/app/backend python3 migrate_recreate_chart_of_accounts_table.py
PYTHONPATH=/app/backend python3 migrate_create_accounting_entries.py
```

## Verification

After running migrations, verify:

1. **Tenants exist**:
   ```sql
   SELECT id, name, business_type FROM tenants;
   ```

2. **All data has tenant_id**:
   ```sql
   SELECT COUNT(*) FROM trucks WHERE tenant_id IS NULL;
   SELECT COUNT(*) FROM chart_of_accounts WHERE tenant_id IS NULL;
   SELECT COUNT(*) FROM journal_entries WHERE tenant_id IS NULL;
   ```
   All should return 0.

3. **Chart of accounts constraint**:
   ```sql
   SELECT sql FROM sqlite_master WHERE type='table' AND name='chart_of_accounts';
   ```
   Should show `UNIQUE (tenant_id, code)` not `UNIQUE (code)`.

4. **Accounting entries created**:
   ```sql
   SELECT COUNT(*) FROM journal_entries;
   SELECT COUNT(*) FROM chart_of_accounts;
   ```

## Rollback (If Needed)

If you need to rollback:

1. The `migrate_recreate_chart_of_accounts_table.py` script creates a backup table `chart_of_accounts_backup` before making changes. If something goes wrong, it will attempt to restore automatically.

2. For other migrations, you may need to manually restore from a database backup.

## Notes

- All migrations are idempotent - safe to run multiple times
- Migrations check for existing data/columns before making changes
- The `migrate_create_accounting_entries.py` script skips entries that already exist
- Make sure to backup your database before running migrations in production

