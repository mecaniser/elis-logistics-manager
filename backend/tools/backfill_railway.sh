#!/bin/bash
# Script to backfill settlements to Railway database using Railway CLI
# Requires Railway CLI to be installed and linked

set -e  # Exit on error

echo "🚂 Backfilling settlements to Railway database (via Railway CLI)..."
echo ""

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

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Error: Railway CLI not found"
    echo "   Install it: npm i -g @railway/cli"
    exit 1
fi

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
    echo ""
    read -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi
    echo ""
fi

# Run the ingest script in Railway's environment
echo "🔄 Running ingestion script in Railway environment...\n"
railway run python backend/tools/ingest_consolidated_settlements.py \
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

exit $EXIT_CODE

