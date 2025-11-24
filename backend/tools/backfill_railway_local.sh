#!/bin/bash
# Script to backfill settlements to Railway database from local machine
# Requires DATABASE_URL environment variable to be set

echo "🚂 Backfilling settlements to Railway database (local connection)..."
echo ""

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL environment variable is not set"
    echo ""
    echo "To get your Railway DATABASE_URL:"
    echo "1. Go to Railway dashboard"
    echo "2. Click on your PostgreSQL service"
    echo "3. Go to 'Variables' tab"
    echo "4. Copy the DATABASE_URL value"
    echo ""
    echo "Then run:"
    echo "  export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
    echo "  ./backend/tools/backfill_railway_local.sh"
    exit 1
fi

# Make sure we're in the right directory
cd "$(dirname "$0")/../.."

# Activate virtual environment
source backend/venv/bin/activate

# Run the ingest script
python backend/tools/ingest_consolidated_settlements.py \
  backend/417_consolidated_settlement.json \
  backend/418_consolidated_settlement.json

echo ""
echo "✅ Backfill complete!"
echo ""
echo "⚠️  Remember to unset DATABASE_URL when done:"
echo "   unset DATABASE_URL"

