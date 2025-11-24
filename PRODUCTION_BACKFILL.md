# Production Backfill Quick Reference

## Quick Start

### Step 1: Test with Dry-Run (Recommended)

```bash
# Using local connection
export DATABASE_URL='your-railway-postgresql-url'
./backend/tools/backfill_production.sh --method local --dry-run --verbose

# Or using Railway CLI
./backend/tools/backfill_production.sh --method railway --dry-run --verbose
```

### Step 2: Run Actual Backfill

```bash
# Using local connection
./backend/tools/backfill_production.sh --method local --verbose

# Or using Railway CLI  
./backend/tools/backfill_production.sh --method railway --verbose
```

## What Was Created

1. **Enhanced ingestion script** (`backend/tools/ingest_consolidated_settlements.py`)
   - Better error handling
   - Dry-run support
   - Verbose output
   - Truck verification
   - Detailed statistics

2. **Comprehensive backfill script** (`backend/tools/backfill_production.sh`)
   - Supports both local and Railway CLI methods
   - Automatic file discovery
   - Safety confirmations
   - Better error messages

3. **Updated existing scripts**
   - `backend/tools/backfill_railway_local.sh` - Enhanced with dry-run and verbose
   - `backend/tools/backfill_railway.sh` - Enhanced with dry-run and verbose

4. **Documentation**
   - `backend/tools/BACKFILL_README.md` - Complete guide

## Files to Backfill

The scripts will automatically find and process:
- `backend/417_consolidated_settlement.json`
- `backend/418_consolidated_settlement.json`

Or specify custom files:
```bash
./backend/tools/backfill_production.sh --files backend/417_consolidated_settlement.json
```

## Important Notes

1. **Always run dry-run first** to see what will happen
2. **Ensure trucks exist** in the database before importing settlements
3. **The script will upsert** - it inserts new settlements or updates existing ones
4. **Unset DATABASE_URL** after using local method to avoid accidental production writes

## Getting Railway DATABASE_URL

1. Go to Railway dashboard
2. Click on your PostgreSQL service
3. Go to 'Variables' tab
4. Copy the `DATABASE_URL` value

## Troubleshooting

- **"Trucks don't exist"**: Create trucks in database first
- **"File not found"**: Check file paths are correct
- **"Database connection failed"**: Verify DATABASE_URL or Railway CLI connection

For detailed help, see `backend/tools/BACKFILL_README.md`

