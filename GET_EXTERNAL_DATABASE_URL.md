# How to Get External DATABASE_URL from Railway

The `postgres.railway.internal` hostname only works **inside Railway's network**. For local import, you need the **external/public** connection string.

## Method 1: Railway Dashboard (Easiest)

1. Go to Railway dashboard
2. Click on your **PostgreSQL service**
3. Go to **"Connect"** or **"Data"** tab
4. Look for **"Public Network"** or **"Connection String"**
5. Copy the external DATABASE_URL
   - Should look like: `postgresql://postgres:pass@containers-us-west-xxx.railway.app:5432/railway`
   - NOT `postgres.railway.internal` (that's internal only)

## Method 2: Railway CLI

```bash
# Get all variables (might show external URL)
railway variables

# Or check PostgreSQL service specifically
railway service
```

## Method 3: Use Railway Connect (Alternative)

If Railway doesn't expose PostgreSQL publicly, you can:

1. **Use Railway's built-in import** (if available)
2. **Create a temporary API endpoint** to import data
3. **Use Railway's database proxy** (if available)

## Quick Import Once You Have External URL

Once you have the external DATABASE_URL:

```bash
# Set the external DATABASE_URL
export DATABASE_URL="postgresql://postgres:pass@external-host.railway.app:5432/railway"

# Run import
cd backend
source venv/bin/activate
python import_consolidated_settlements.py \
  ../settlements_extracted/settlements_consolidated.json \
  --clear-existing

# Unset for safety
unset DATABASE_URL
```

## Note

If Railway PostgreSQL doesn't expose a public connection string (for security), you'll need to:
- Use `railway run` but ensure it executes in Railway's environment
- Or create a temporary import endpoint in your FastAPI app
- Or use Railway's database import feature (if available)

