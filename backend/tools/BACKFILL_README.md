# Production Database Backfill Guide

This guide explains how to backfill your production database with consolidated settlement JSON files.

## Overview

The backfill process imports settlement data from consolidated JSON files into your production database. The system supports:
- **Upsert operations**: Inserts new settlements or updates existing ones
- **Truck matching**: Automatically matches settlements to trucks by license plate or unit number
- **Dry-run mode**: Test the import without making changes
- **Verbose output**: See detailed progress and changes

## Prerequisites

1. **Consolidated JSON files**: Files named `*_consolidated_settlement.json` in the `backend/` directory
2. **Trucks in database**: All trucks referenced in settlements must exist in the database
3. **Database access**: Either Railway DATABASE_URL or Railway CLI access

## Quick Start

### Option 1: Using Local Connection (Recommended for Testing)

1. **Get your Railway DATABASE_URL**:
   - Go to Railway dashboard
   - Click on your PostgreSQL service
   - Go to 'Variables' tab
   - Copy the `DATABASE_URL` value

2. **Set the environment variable**:
   ```bash
   export DATABASE_URL='postgresql://user:pass@host:port/dbname'
   ```

3. **Run dry-run first** (recommended):
   ```bash
   ./backend/tools/backfill_production.sh --method local --dry-run --verbose
   ```

4. **Run the actual backfill**:
   ```bash
   ./backend/tools/backfill_production.sh --method local --verbose
   ```

5. **Unset DATABASE_URL when done**:
   ```bash
   unset DATABASE_URL
   ```

### Option 2: Using Railway CLI

1. **Install Railway CLI** (if not already installed):
   ```bash
   npm i -g @railway/cli
   ```

2. **Link your project** (if not already linked):
   ```bash
   railway link
   ```

3. **Run dry-run first**:
   ```bash
   ./backend/tools/backfill_production.sh --method railway --dry-run --verbose
   ```

4. **Run the actual backfill**:
   ```bash
   ./backend/tools/backfill_production.sh --method railway --verbose
   ```

## Available Scripts

### 1. Comprehensive Backfill Script (Recommended)

**File**: `backend/tools/backfill_production.sh`

The most flexible script that supports both methods and all options.

```bash
# Show help
./backend/tools/backfill_production.sh --help

# Dry run with verbose output
./backend/tools/backfill_production.sh --method local --dry-run --verbose

# Backfill specific files
./backend/tools/backfill_production.sh --method local --files backend/417_consolidated_settlement.json
```

### 2. Local Connection Script

**File**: `backend/tools/backfill_railway_local.sh`

Simplified script for local connections only.

```bash
export DATABASE_URL='postgresql://...'
./backend/tools/backfill_railway_local.sh --dry-run --verbose
./backend/tools/backfill_railway_local.sh --verbose
```

### 3. Railway CLI Script

**File**: `backend/tools/backfill_railway.sh`

Simplified script for Railway CLI only.

```bash
./backend/tools/backfill_railway.sh --dry-run --verbose
./backend/tools/backfill_railway.sh --verbose
```

### 4. Direct Python Script

**File**: `backend/tools/ingest_consolidated_settlements.py`

Run the Python script directly for maximum control.

```bash
# Activate virtual environment
source backend/venv/bin/activate

# Dry run
python backend/tools/ingest_consolidated_settlements.py \
  --dry-run \
  --verbose \
  backend/417_consolidated_settlement.json \
  backend/418_consolidated_settlement.json

# Actual import
python backend/tools/ingest_consolidated_settlements.py \
  --verbose \
  backend/417_consolidated_settlement.json \
  backend/418_consolidated_settlement.json
```

## Understanding the Output

### Dry-Run Output

When running with `--dry-run`, you'll see:
- ✅ **Insert**: New settlements that would be added
- ✏️ **Update**: Existing settlements that would be updated (with field changes)
- ✓ **No changes**: Existing settlements that are already up-to-date
- ⚠️ **Skipped**: Settlements that couldn't be matched to trucks

### Summary Output

After processing, you'll see a summary:
```
📊 IMPORT SUMMARY
============================================================
Files processed: 2
  - backend/417_consolidated_settlement.json: 45 entries
  - backend/418_consolidated_settlement.json: 67 entries

Total entries: 112
✅ Inserted: 98
✏️  Updated: 12
⏭️  Skipped (no changes): 2
⚠️  Skipped (unresolved truck): 0
```

## Troubleshooting

### Error: "Some trucks referenced in settlements do not exist"

**Solution**: Create the missing trucks in the database first. The script will list which trucks are missing.

### Error: "No truck found for unit X, plate Y"

**Solution**: 
1. Check that the truck exists in the database
2. Verify the truck's `name` field matches the unit number (e.g., "417" or "Volvo 417")
3. Verify the truck's `license_plate` matches the plate number
4. Check `license_plate_history` if the plate has changed

### Error: "Database connection failed"

**Solution**:
- Verify DATABASE_URL is set correctly
- Check network connectivity
- Ensure Railway database is running
- Try using Railway CLI method instead

### Settlements not updating

**Solution**:
- Check that `truck_id` and `settlement_date` match exactly
- Use `--verbose` to see what changes would be made
- Verify the JSON file has the correct data

## How It Works

1. **Load JSON files**: Reads consolidated settlement JSON files
2. **Normalize entries**: Converts JSON format to database format
3. **Match trucks**: Uses license plate or unit number to find truck_id
4. **Calculate loan interest**: Adds weekly loan interest to expenses if truck has a loan
5. **Upsert settlements**: Inserts new or updates existing settlements based on truck_id + settlement_date

## Data Matching Strategy

The script tries multiple strategies to match settlements to trucks:

1. **License plate match**: Exact match on `license_plate` field
2. **Unit number match**: Exact match on `name` field (e.g., "417")
3. **Volvo format match**: Match on "Volvo {number}" format
4. **License plate history**: Check `license_plate_history` JSON array

## Safety Features

- **Dry-run mode**: Test without making changes
- **Truck verification**: Ensures trucks exist before importing
- **Transaction safety**: All changes are committed in a single transaction
- **Error handling**: Continues processing even if individual entries fail
- **Confirmation prompt**: Asks for confirmation before modifying production database

## Best Practices

1. **Always run dry-run first**: Use `--dry-run --verbose` to see what will happen
2. **Backup first**: Consider backing up your database before large imports
3. **Import incrementally**: Test with one file first, then import all files
4. **Monitor output**: Watch for unresolved trucks or errors
5. **Verify results**: Check the database after import to ensure data is correct

## File Format

Consolidated settlement files should have this structure:

```json
[
  {
    "unit_number": "417",
    "plate_number": "VV9952",
    "statement": {
      "statement_id": "SETT-2024-12-14-417",
      "period_start": "2024-12-08",
      "period_end": "2024-12-14",
      "source_file": "ELIS LOGISTICS LLC #417 - 12-14-24.pdf"
    },
    "blocks_count": 1,
    "block_ids": [
      {
        "block_id": "ZK6S-CLT9",
        "delivery_date": "2024-12-08"
      }
    ],
    "statement_totals": {
      "gross_miles": 779.0,
      "gross_revenue": 2110.9,
      "total_driver_pay": 600.0,
      "fuel": 0.0,
      "dispatch_fee_total": 168.87,
      "net_to_owner": 500.88
    }
  }
]
```

## Support

If you encounter issues:
1. Check the verbose output (`--verbose`)
2. Review the error messages
3. Verify your JSON file format matches the expected structure
4. Ensure all trucks exist in the database

