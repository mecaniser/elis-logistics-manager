#!/bin/bash
# Script to backfill settlements to Railway database from local machine
# Requires DATABASE_URL environment variable to be set

set -e  # Exit on error

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
    echo "  ./backend/tools/backfill_railway_local.sh [--dry-run] [--verbose]"
    exit 1
fi

# Parse arguments
DRY_RUN=""
VERBOSE=""
for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        *)
            # Unknown option
            ;;
    esac
done

# Make sure we're in the right directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo "❌ Error: Virtual environment not found at backend/venv"
    echo "   Please create it first: python3 -m venv backend/venv"
    exit 1
fi

# Activate virtual environment
source backend/venv/bin/activate

# Check if JSON files exist
MISSING_FILES=()
for file in "backend/417_consolidated_settlement.json" "backend/418_consolidated_settlement.json"; do
    if [ ! -f "$file" ]; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo "❌ Error: Missing required files:"
    for file in "${MISSING_FILES[@]}"; do
        echo "   - $file"
    done
    exit 1
fi

# Confirm before proceeding (unless dry-run)
if [ -z "$DRY_RUN" ]; then
    echo "⚠️  WARNING: This will modify the production database!"
    echo "   Database: $DATABASE_URL"
    echo ""
    read -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi
    echo ""
fi

# Run the ingest script
echo "🔄 Running ingestion script...\n"
python backend/tools/ingest_consolidated_settlements.py \
  $DRY_RUN \
  $VERBOSE \
  backend/417_consolidated_settlement.json \
  backend/418_consolidated_settlement.json

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Backfill complete!"
else
    echo ""
    echo "❌ Backfill failed with exit code $EXIT_CODE"
fi

echo ""
echo "⚠️  Remember to unset DATABASE_URL when done:"
echo "   unset DATABASE_URL"

exit $EXIT_CODE

