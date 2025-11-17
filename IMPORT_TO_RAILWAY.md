# Import Data to Railway PostgreSQL

This guide shows you how to import your local data to Railway PostgreSQL database.

## Prerequisites

1. Railway project deployed with PostgreSQL database
2. Local data file ready (JSON export or consolidated settlements)
3. Railway CLI installed (optional, for Method 1)

## Method 1: Using Railway CLI (Recommended)

This method runs the import script directly in Railway's environment with access to the production database.

### Step 1: Install Railway CLI

```bash
npm i -g @railway/cli
```

### Step 2: Login and Link

```bash
# Login to Railway
railway login

# Navigate to your project directory
cd /Users/sergio/GitHub/elis-logistics-app

# Link to your Railway project
railway link
```

### Step 3: Run Import Script

```bash
# Import consolidated settlements
railway run python backend/import_consolidated_settlements.py \
  backend/settlements_extracted/settlements_consolidated.json \
  --clear-existing

# Or import regular settlements export
railway run python backend/import_settlements.py \
  backend/settlements_export.json \
  --force
```

**Options:**
- `--clear-existing` - Delete all existing settlements before import
- `--update-existing` - Update existing settlements instead of skipping
- `--skip-existing` - Skip duplicates (default behavior)

### Step 4: Verify Import

```bash
# Connect to Railway PostgreSQL shell
railway connect postgres

# Then run SQL queries:
\dt                    # List all tables
SELECT COUNT(*) FROM settlements;  # Count settlements
SELECT COUNT(*) FROM trucks;        # Count trucks
```

## Method 2: Using DATABASE_URL Locally

This method connects your local machine directly to Railway PostgreSQL.

### Step 1: Get DATABASE_URL from Railway

1. Go to Railway dashboard
2. Click on your **PostgreSQL service**
3. Go to **Variables** tab
4. Copy the `DATABASE_URL` value
   - Format: `postgresql://user:password@host:port/dbname`

### Step 2: Set Environment Variable

```bash
# Set DATABASE_URL (replace with your actual URL)
export DATABASE_URL="postgresql://postgres:password@host.railway.app:5432/railway"

# Verify it's set
echo $DATABASE_URL
```

### Step 3: Run Import Script

```bash
cd backend

# Activate virtual environment (if using one)
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate      # On Windows

# Run import script
python import_consolidated_settlements.py \
  settlements_extracted/settlements_consolidated.json \
  --clear-existing
```

### Step 4: Unset Environment Variable (Important!)

After import, unset the DATABASE_URL to avoid accidentally modifying production:

```bash
unset DATABASE_URL
```

## Method 3: Export from Local, Import to Railway

If you want to export from local SQLite first, then import to Railway:

### Step 1: Export from Local Database

```bash
cd backend
source venv/bin/activate
python export_settlements.py -o settlements_export.json
```

### Step 2: Import to Railway

Use Method 1 or Method 2 above to import the exported JSON file.

## Available Import Scripts

### 1. `import_consolidated_settlements.py`
**Purpose:** Import consolidated settlements JSON format

**Usage:**
```bash
python import_consolidated_settlements.py <json_file> [options]
```

**Options:**
- `--clear-existing` - Delete all existing settlements first
- `--update-existing` - Update existing settlements
- `--skip-existing` - Skip duplicates (default)

**Example:**
```bash
python import_consolidated_settlements.py \
  settlements_extracted/settlements_consolidated.json \
  --clear-existing
```

### 2. `import_settlements.py`
**Purpose:** Import regular settlements export format

**Usage:**
```bash
python import_settlements.py <json_file> [--force]
```

**Example:**
```bash
python import_settlements.py settlements_export.json --force
```

### 3. `import_json_settlements.py`
**Purpose:** Import individual settlement JSON files

**Usage:**
```bash
python import_json_settlements.py <json_file>
```

## Import Process Details

### What Gets Imported

1. **Trucks** - Automatically created if they don't exist
2. **Settlements** - All settlement records with:
   - Revenue data
   - Expense categories
   - Metrics (miles, blocks)
   - Dates and periods

### What Doesn't Get Imported

- **PDF files** - Only metadata is imported (no actual PDF files)
- **Repairs** - Use separate repair import if needed
- **Drivers** - Created if referenced in settlements

### Duplicate Handling

By default, the script **skips** settlements that already exist (same `truck_id` + `settlement_date`).

To overwrite duplicates:
```bash
--update-existing  # Update existing records
--clear-existing   # Delete all first, then import
```

## Troubleshooting

### Error: "Could not find truck with license plate"

**Solution:** The script automatically creates trucks, but if you have custom trucks:
1. Create trucks manually via Railway API or dashboard
2. Or modify `ensure_trucks_exist()` function in the import script

### Error: "Connection refused" or "Could not connect"

**Solution:**
1. Verify DATABASE_URL is correct
2. Check Railway PostgreSQL service is running (green status)
3. Ensure your IP is allowed (Railway PostgreSQL is usually accessible from anywhere)

### Error: "Table does not exist"

**Solution:** Tables should auto-create, but you can force creation:
```bash
# Using Railway CLI
railway run python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### Import is Slow

**Solution:** 
- Large imports may take time
- Script shows progress every 10 records
- Be patient for large datasets

## Verification Steps

After import, verify data:

### Using Railway CLI

```bash
# Connect to database
railway connect postgres

# Check counts
SELECT COUNT(*) FROM settlements;
SELECT COUNT(*) FROM trucks;
SELECT COUNT(*) FROM repairs;

# View sample data
SELECT * FROM settlements LIMIT 5;
SELECT * FROM trucks;
```

### Using Railway Dashboard

1. Go to Railway dashboard → PostgreSQL service
2. Click **"Query"** tab
3. Run SQL queries to verify data

### Using API

```bash
# Get Railway URL
railway domain

# Test API endpoints
curl https://your-app.railway.app/api/settlements
curl https://your-app.railway.app/api/trucks
curl https://your-app.railway.app/api/analytics/dashboard
```

## Best Practices

1. **Backup First**: Export your Railway data before importing
   ```bash
   railway run python backend/export_settlements.py -o railway_backup.json
   ```

2. **Test Import**: Import to a test database first if possible

3. **Verify Data**: Always check counts and sample data after import

4. **Use Transactions**: Import scripts use database transactions - if import fails, nothing is committed

5. **Clear vs Update**: 
   - Use `--clear-existing` for fresh start
   - Use `--update-existing` to update existing records
   - Use default (skip) to avoid duplicates

## Example: Full Import Workflow

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login and link
railway login
railway link

# 3. Test database connection
railway run python backend/test_db_connection.py

# 4. Import consolidated settlements
railway run python backend/import_consolidated_settlements.py \
  backend/settlements_extracted/settlements_consolidated.json \
  --clear-existing

# 5. Verify import
railway connect postgres
# Then: SELECT COUNT(*) FROM settlements;

# 6. Test API
curl https://your-app.railway.app/api/health
curl https://your-app.railway.app/api/settlements
```

## Security Notes

⚠️ **Important:**
- Never commit DATABASE_URL to git (it's in .gitignore)
- Unset DATABASE_URL after local import
- Railway PostgreSQL credentials are automatically rotated
- Use Railway CLI when possible (more secure)

## Need Help?

- Check `RAILWAY_DEPLOYMENT.md` for deployment details
- Check `DATABASE_CONNECTION.md` for connection info
- Railway logs: `railway logs --follow`
- Database shell: `railway connect postgres`

