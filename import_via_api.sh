#!/bin/bash
# Import settlements via API endpoint (after app is deployed)
# Usage: ./import_via_api.sh <your-railway-app-url>

RAILWAY_URL="${1:-http://localhost:8000}"
JSON_FILE="backend/settlements_extracted/settlements_consolidated.json"

if [ ! -f "$JSON_FILE" ]; then
    echo "❌ JSON file not found: $JSON_FILE"
    exit 1
fi

echo "🚀 Importing settlements via API..."
echo "📍 API URL: $RAILWAY_URL/api/settlements/upload-json"
echo ""

# Read JSON and send to API
curl -X POST "$RAILWAY_URL/api/settlements/upload-json" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -F "json_data=$(cat $JSON_FILE)" \
  | python3 -m json.tool

echo ""
echo "✅ Import completed!"

