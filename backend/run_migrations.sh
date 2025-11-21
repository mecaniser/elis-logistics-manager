#!/bin/bash
# Master migration script to run all loan interest related migrations in order
# Usage: ./run_migrations.sh

set -e  # Exit on error

echo "============================================================"
echo "Running all loan interest migrations in order"
echo "============================================================"
echo ""

# Run migrations in order
echo "1. Adding investment fields..."
python backend/migrate_add_investment_fields.py
echo ""

echo "2. Adding registration fee..."
python backend/migrate_add_registration_fee.py
echo ""

echo "3. Adding interest rate..."
python backend/migrate_add_interest_rate.py
echo ""

echo "4. Adding current loan balance..."
python backend/migrate_add_current_loan_balance.py
echo ""

echo "5. Recalculating loan interest with principal payments..."
python backend/migrate_recalculate_loan_interest_with_principal.py
echo ""

echo "============================================================"
echo "✓ ALL MIGRATIONS COMPLETED SUCCESSFULLY"
echo "============================================================"

