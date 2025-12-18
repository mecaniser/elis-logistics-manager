# Migration: Simplify Elis Logistics Accounts

## Overview

This migration script (`migrate_simplify_elis_logistics_accounts.py`) simplifies the chart of accounts for Elis Logistics LLC by:

1. **Removing per-asset accounting complexity** - Ensures all accounts have `truck_id = NULL` (shared accounts)
2. **Ensuring minimal accounts exist** - Creates/verifies the simplified account structure
3. **Handling account code conflicts** - Resolves conflicts between old and new account codes
4. **Deactivating unused accounts** - Removes accounts that Elis Logistics doesn't use (Fuel, Dispatch Fees, etc.)

## When to Run

Run this migration **after** implementing the simplified accounting system changes:

- ✅ After updating `accounting_service_minimal.py` with new minimal accounts
- ✅ After updating `accounting_service.py` to exclude Elis Logistics from per-asset accounting
- ✅ Before or after creating new journal entries (migration is idempotent)

## What It Does

### Step 1: Ensure Accounts Have `truck_id = NULL`
- Finds all accounts for Elis Logistics LLC that have `truck_id` set
- Updates them to `truck_id = NULL` (shared accounts)

### Step 2: Ensure Minimal Accounts Exist
Creates/verifies these accounts exist:
- **Assets**: Cash (1000), Vehicles & Equipment (1500), Accumulated Depreciation (1600)
- **Liabilities**: Loans Payable (2100), Taxes Payable (2200)
- **Equity**: Owner Equity (3000), Retained Earnings (3100)
- **Revenue**: Settlement Income (4000), **Trailer Rental Income (4100)** ✨ NEW
- **Expenses**: Maintenance & Repairs (5100), **Trailer Expenses (5200)** ✨ NEW, Interest Expense (5300), Depreciation Expense (5400), **Section 179 Deduction (5500)** ✨ NEW

### Step 3: Handle Account Code Conflicts
Resolves conflicts where old account codes are reused for new purposes:
- **5200**: Old "Insurance" → New "Trailer Expenses"
- **5300**: Old "Dispatch Fees" → New "Interest Expense"
- **5400**: Old "Payroll Fees" → New "Depreciation Expense"

If old accounts exist and are unused, they're renamed. If they're in use, they're deactivated and new accounts are created.

### Step 4: Deactivate Unused Accounts
Deactivates (doesn't delete) old accounts that Elis Logistics doesn't use:
- Fuel (5000)
- Fuel Expense (6001)
- Dispatch Fee Expense (6002)
- Insurance Expense (6003)
- Safety Expense (6004)
- Prepass Expense (6005)
- IFTA Expense (6006)
- Driver Pay Expense (6007)
- Payroll Fee Expense (6008)
- Parking Expense (6010)
- Decals Expense (6012)

**Note**: Accounts are only deactivated if they have no journal entry lines referencing them.

### Step 5: Update Journal Entries
- Ensures all journal entries for Elis Logistics have `truck_id = NULL`
- Ensures all journal entry lines have `truck_id = NULL`

## Running the Migration

### Standalone
```bash
cd backend
python3 migrate_simplify_elis_logistics_accounts.py
```

### Via Master Migration Script
```bash
cd backend
python3 run_all_production_migrations.py
```

The migration is included in the master migration script and will run automatically.

## Safety

- ✅ **Idempotent**: Safe to run multiple times
- ✅ **Non-destructive**: Doesn't delete accounts, only deactivates unused ones
- ✅ **Checks before changes**: Verifies account usage before deactivating
- ✅ **Preserves data**: Journal entries and lines are preserved, only `truck_id` is updated

## Verification

After running the migration, verify:

1. **All accounts have `truck_id = NULL`**:
   ```sql
   SELECT COUNT(*) FROM chart_of_accounts 
   WHERE tenant_id = <elis_tenant_id> AND truck_id IS NOT NULL;
   -- Should return 0
   ```

2. **Minimal accounts exist**:
   ```sql
   SELECT code, name FROM chart_of_accounts 
   WHERE tenant_id = <elis_tenant_id> AND truck_id IS NULL AND is_active = 1
   ORDER BY code;
   -- Should show only the minimal accounts listed above
   ```

3. **Journal entries have `truck_id = NULL`**:
   ```sql
   SELECT COUNT(*) FROM journal_entries 
   WHERE tenant_id = <elis_tenant_id> AND truck_id IS NOT NULL;
   -- Should return 0
   ```

## Rollback

If needed, you can manually reactivate accounts:
```sql
UPDATE chart_of_accounts SET is_active = 1 WHERE tenant_id = <elis_tenant_id>;
```

However, the migration changes account names and `truck_id` values, so a full rollback would require a database backup restore.

