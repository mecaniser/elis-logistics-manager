# Railway Post-Deployment Checklist

## ✅ After Database is Deployed

Once your PostgreSQL database is deployed in Railway, follow these steps:

### Step 1: Verify Database Connection

```bash
# Test database connection
railway run python backend/test_db_connection.py
```

**Expected output:**
```
🔍 Testing Database Connection...
--------------------------------------------------
Database URL: postgresql://user:****@host:port/dbname
Database Type: PostgreSQL
--------------------------------------------------
⏳ Connecting to database...
✅ Connection successful!
📊 PostgreSQL Version: PostgreSQL 15.x
📋 Tables found: 0
   (No tables found - tables will be created on first app startup)
--------------------------------------------------
✅ Database connection test passed!
```

### Step 2: Verify Tables Are Created

Tables are automatically created when your FastAPI app starts. Check if tables exist:

```bash
# Connect to PostgreSQL shell
railway connect postgres

# Then run:
\dt                    # List all tables
```

**Expected tables:**
- `trucks`
- `settlements`
- `repairs`
- `drivers`

If tables don't exist yet, they will be created automatically when your app starts for the first time.

### Step 3: Import Your Data

Once database is ready and tables exist, import your consolidated settlements:

```bash
# Import consolidated settlements
railway run python backend/import_consolidated_settlements.py \
  backend/settlements_extracted/settlements_consolidated.json \
  --clear-existing
```

**What this does:**
- Creates trucks if they don't exist
- Imports all settlements from JSON file
- `--clear-existing` removes any existing settlements first (fresh start)

### Step 4: Verify Import

```bash
# Connect to database
railway connect postgres

# Check counts
SELECT COUNT(*) FROM settlements;
SELECT COUNT(*) FROM trucks;

# View sample data
SELECT * FROM settlements LIMIT 5;
SELECT * FROM trucks;
```

### Step 5: Test Your Application

```bash
# Get your Railway URL
railway domain

# Test API endpoints
curl https://your-app.railway.app/api/health
curl https://your-app.railway.app/api/settlements
curl https://your-app.railway.app/api/trucks
curl https://your-app.railway.app/api/analytics/dashboard
```

## 🔄 Import Options

### Option 1: Clear and Import (Fresh Start)
```bash
railway run python backend/import_consolidated_settlements.py \
  backend/settlements_extracted/settlements_consolidated.json \
  --clear-existing
```
**Use when:** Starting fresh, want to replace all data

### Option 2: Update Existing
```bash
railway run python backend/import_consolidated_settlements.py \
  backend/settlements_extracted/settlements_consolidated.json \
  --update-existing
```
**Use when:** Want to update existing settlements

### Option 3: Skip Duplicates (Default)
```bash
railway run python backend/import_consolidated_settlements.py \
  backend/settlements_extracted/settlements_consolidated.json
```
**Use when:** Only want to add new settlements, keep existing ones

## 📋 Quick Reference Commands

```bash
# Test connection
railway run python backend/test_db_connection.py

# Import data
railway run python backend/import_consolidated_settlements.py \
  backend/settlements_extracted/settlements_consolidated.json \
  --clear-existing

# Connect to database
railway connect postgres

# View logs
railway logs --follow

# Get Railway URL
railway domain
```

## ⚠️ Important Notes

1. **Tables Auto-Create**: Tables are created automatically when FastAPI app starts
2. **First Startup**: Make sure your app has started at least once before importing
3. **Trucks Created**: Import script automatically creates trucks if they don't exist
4. **No PDFs**: Import only includes metadata, not actual PDF files
5. **Backup First**: Consider exporting Railway data before importing (if any exists)

## 🐛 Troubleshooting

### "Table does not exist"
**Solution:** Start your app first - tables are created on startup
```bash
# Check if app is running
railway status

# If not running, trigger a deployment or restart
```

### "Could not connect to database"
**Solution:** 
- Verify PostgreSQL service is running (green status in Railway)
- Check DATABASE_URL is set correctly
- Test connection: `railway run python backend/test_db_connection.py`

### "Could not find truck with license plate"
**Solution:** Import script creates trucks automatically, but if you have custom trucks:
- Create them manually via API first
- Or modify `ensure_trucks_exist()` in import script

## ✅ Success Indicators

After successful import, you should see:
- ✅ Connection test passes
- ✅ Tables exist (trucks, settlements, repairs, drivers)
- ✅ Settlement count matches your JSON file
- ✅ API endpoints return data
- ✅ Dashboard shows analytics


