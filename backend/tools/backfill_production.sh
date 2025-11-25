#!/bin/bash
# Comprehensive production backfill script
# Handles all scenarios for backfilling settlements to production database

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
METHOD="local"
DRY_RUN=""
VERBOSE=""
FILES=""

# Parse arguments
show_help() {
    cat << EOF
Production Backfill Script for Elis Logistics App

Usage: $0 [OPTIONS]

Options:
    --method METHOD       Method to use: 'local' (default) or 'railway'
                         - local: Uses DATABASE_URL env var
                         - railway: Uses Railway CLI
    --dry-run            Test run without writing to database
    --verbose, -v         Show detailed progress
    --files FILES        Comma-separated list of JSON files (default: all consolidated files)
    --help, -h           Show this help message

Examples:
    # Dry run with local connection
    export DATABASE_URL='postgresql://...'
    $0 --method local --dry-run --verbose

    # Backfill via Railway CLI
    $0 --method railway --verbose

    # Backfill specific files
    $0 --files backend/417_consolidated_settlement.json

EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --method)
            METHOD="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --files)
            FILES="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🚂 Production Backfill Script${NC}"
echo ""

# Determine which files to process
if [ -z "$FILES" ]; then
    # Default: find all consolidated settlement files
    FILES=$(find backend -maxdepth 1 -name "*_consolidated_settlement.json" -type f | sort | tr '\n' ' ')
    if [ -z "$FILES" ]; then
        echo -e "${RED}❌ Error: No consolidated settlement files found${NC}"
        echo "   Expected files: backend/*_consolidated_settlement.json"
        exit 1
    fi
else
    # Convert comma-separated to space-separated
    FILES=$(echo "$FILES" | tr ',' ' ')
fi

echo -e "${BLUE}Files to process:${NC}"
for file in $FILES; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo -e "  ${RED}✗ $file (not found)${NC}"
        exit 1
    fi
done
echo ""

# Method-specific setup
if [ "$METHOD" = "local" ]; then
    if [ -z "$DATABASE_URL" ]; then
        echo -e "${RED}❌ Error: DATABASE_URL environment variable is not set${NC}"
        echo ""
        echo "To get your Railway DATABASE_URL:"
        echo "1. Go to Railway dashboard"
        echo "2. Click on your PostgreSQL service"
        echo "3. Go to 'Variables' tab"
        echo "4. Copy the DATABASE_URL value"
        echo ""
        echo "Then run:"
        echo "  export DATABASE_URL='postgresql://user:pass@host:port/dbname'"
        echo "  $0 --method local"
        exit 1
    fi
    
    # Check if virtual environment exists
    if [ ! -d "backend/venv" ]; then
        echo -e "${RED}❌ Error: Virtual environment not found at backend/venv${NC}"
        echo "   Please create it first: python3 -m venv backend/venv"
        exit 1
    fi
    
    # Activate virtual environment
    source backend/venv/bin/activate
    
    echo -e "${BLUE}Method:${NC} Local connection (DATABASE_URL)"
    echo -e "${BLUE}Database:${NC} $(echo $DATABASE_URL | sed 's/:[^:]*@/:***@/')"
    
    # Build command
    CMD="python backend/tools/ingest_consolidated_settlements.py $DRY_RUN $VERBOSE $FILES"
    
elif [ "$METHOD" = "railway" ]; then
    # Check if Railway CLI is installed
    if ! command -v railway &> /dev/null; then
        echo -e "${RED}❌ Error: Railway CLI not found${NC}"
        echo "   Install it: npm i -g @railway/cli"
        exit 1
    fi
    
    echo -e "${BLUE}Method:${NC} Railway CLI"
    
    # Build command
    CMD="railway run python backend/tools/ingest_consolidated_settlements.py $DRY_RUN $VERBOSE $FILES"
    
else
    echo -e "${RED}❌ Error: Invalid method '$METHOD'${NC}"
    echo "   Valid methods: 'local' or 'railway'"
    exit 1
fi

# Confirm before proceeding (unless dry-run)
if [ -z "$DRY_RUN" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  WARNING: This will modify the production database!${NC}"
    read -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi
    echo ""
fi

# Run the command
echo -e "${BLUE}🔄 Running ingestion...${NC}\n"
eval $CMD

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Backfill complete!${NC}"
else
    echo -e "${RED}❌ Backfill failed with exit code $EXIT_CODE${NC}"
fi

# Reminder about DATABASE_URL
if [ "$METHOD" = "local" ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Remember to unset DATABASE_URL when done:${NC}"
    echo "   unset DATABASE_URL"
fi

exit $EXIT_CODE


