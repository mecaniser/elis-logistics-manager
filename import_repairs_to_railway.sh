#!/bin/bash
# Import repairs to Railway PostgreSQL
# This script will use the Railway DATABASE_URL to import repairs

RAILWAY_DATABASE_URL="postgresql://postgres:xPBUIyAPqAklsYoyvchydMhUYJnbtiot@mainline.proxy.rlwy.net:22169/railway"

echo "🚀 Importing repairs to Railway PostgreSQL..."
echo ""

# Check if virtual environment exists
if [ ! -d "backend/venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
    cd ..
else
    echo "✅ Virtual environment found"
fi

# Activate virtual environment
cd backend
source venv/bin/activate

# Check if repairs export file exists
REPAIRS_FILE="repairs_export.json"
if [ ! -f "$REPAIRS_FILE" ]; then
    echo "❌ Repairs file not found: $REPAIRS_FILE"
    exit 1
fi

echo "📁 Repairs file found: $REPAIRS_FILE"
echo ""

# Ask for confirmation
read -p "⚠️  This will import repairs to Railway PostgreSQL (duplicates will be skipped). Continue? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Import cancelled"
    exit 1
fi

echo ""
echo "🔄 Starting import..."
echo ""

# Run import script with Railway DATABASE_URL
DATABASE_URL="$RAILWAY_DATABASE_URL" python3 import_repairs.py "$REPAIRS_FILE" --skip-existing

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Import completed successfully!"
    echo ""
    echo "📊 Verify the import in your Railway dashboard or via the Repairs page in the UI."
else
    echo ""
    echo "❌ Import failed. Check the error messages above."
    exit 1
fi

