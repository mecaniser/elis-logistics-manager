# Railway Migration: Add custom_expense_descriptions Column

## Problem
After adding the `custom_expense_descriptions` field to the Settlement model, Railway database needs the column added.

## Solution

### Option 1: Run Migration Script via Railway CLI (Recommended)

1. **Install Railway CLI** (if not already installed):
   ```bash
   npm install -g @railway/cli
   ```

2. **Login to Railway**:
   ```bash
   railway login
   ```

3. **Link to your project**:
   ```bash
   railway link
   ```

4. **Run the migration**:
   ```bash
   railway run python backend/migrate_add_custom_expense_descriptions.py
   ```

### Option 2: Run Migration via Railway Shell

1. Go to Railway dashboard
2. Click on your FastAPI service
3. Click "Shell" tab
4. Run:
   ```bash
   cd /app
   python backend/migrate_add_custom_expense_descriptions.py
   ```

### Option 3: Manual SQL (if above don't work)

1. Go to Railway dashboard
2. Click on your PostgreSQL database
3. Click "Query" tab
4. Run:
   ```sql
   ALTER TABLE settlements ADD COLUMN IF NOT EXISTS custom_expense_descriptions JSONB;
   ```

## Verify Migration

After running the migration, verify it worked:

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'settlements' AND column_name = 'custom_expense_descriptions';
```

You should see:
```
custom_expense_descriptions | jsonb
```

## Notes

- The migration script works for both SQLite (local) and PostgreSQL (Railway)
- The column is nullable, so existing records will have `NULL` for this field
- After migration, restart your FastAPI service in Railway


