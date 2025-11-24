#!/bin/bash
# Script to backfill settlements to Railway database
# Requires Railway CLI to be installed and linked

echo "🚂 Backfilling settlements to Railway database..."
echo ""

# Make sure we're in the right directory
cd "$(dirname "$0")/../.."

# Run the ingest script in Railway's environment
railway run python backend/tools/ingest_consolidated_settlements.py \
  backend/417_consolidated_settlement.json \
  backend/418_consolidated_settlement.json

echo ""
echo "✅ Backfill complete!"

