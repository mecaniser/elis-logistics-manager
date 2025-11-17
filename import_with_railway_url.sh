#!/bin/bash
# Import script using Railway DATABASE_URL
# This script will use the DATABASE_URL you provide

echo "🚀 Importing settlements to Railway PostgreSQL..."
echo ""

# Check if DATABASE_URL is provided
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not set"
    echo ""
    echo "Usage:"
    echo "  export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
    echo "  ./import_with_railway_url.sh"
    echo ""
    echo "Or provide it inline:"
    echo "  DATABASE_URL='postgresql://...' ./import_with_railway_url.sh"
    exit 1
fi

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

# Check if data file exists
DATA_FILE="../settlements_extracted/settlements_consolidated.json"
if [ ! -f "$DATA_FILE" ]; then
    echo "❌ Data file not found: $DATA_FILE"
    exit 1
fi

echo "📁 Data file found: $DATA_FILE"
echo ""

# Ask for confirmation
read -p "⚠️  This will import settlements to Railway PostgreSQL. Continue? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Import cancelled"
    exit 1
fi

echo ""
echo "🔄 Starting import..."
echo ""

# Run import script with DATABASE_URL
python import_consolidated_settlements.py "$DATA_FILE" --clear-existing

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Import completed successfully!"
    echo ""
    echo "📊 Verify the import:"
    echo "  railway connect postgres"
    echo "  Then run: SELECT COUNT(*) FROM settlements;"
else
    echo ""
    echo "❌ Import failed. Check the error messages above."
    exit 1
fi

# Unset DATABASE_URL for safety
unset DATABASE_URL

