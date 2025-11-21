#!/usr/bin/env python3
"""
Migration script to retroactively add loan interest to all existing settlements
Works with both SQLite (local) and PostgreSQL (Railway)
"""
import sys
import os
import json

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL, get_db
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.utils.loan_interest import calculate_weekly_loan_interest
from sqlalchemy.orm import Session

def migrate_add_loan_interest():
    """Add loan interest to all existing settlements retroactively"""
    
    db: Session = next(get_db())
    
    try:
        # Get all settlements
        settlements = db.query(Settlement).all()
        updated_count = 0
        
        for settlement in settlements:
            # Get the truck for this settlement
            truck = db.query(Truck).filter(Truck.id == settlement.truck_id).first()
            
            if not truck or truck.vehicle_type != 'truck':
                continue
            
            # Check if truck has a loan
            loan_amount = float(truck.loan_amount) if truck.loan_amount else None
            interest_rate = float(truck.interest_rate) if truck.interest_rate else 0.07
            
            if not loan_amount or loan_amount <= 0:
                continue
            
            # Calculate weekly interest
            weekly_interest = calculate_weekly_loan_interest(loan_amount, interest_rate)
            
            if weekly_interest <= 0:
                continue
            
            # Get current expense_categories
            expense_categories = {}
            if settlement.expense_categories:
                if isinstance(settlement.expense_categories, str):
                    try:
                        expense_categories = json.loads(settlement.expense_categories)
                    except json.JSONDecodeError:
                        expense_categories = {}
                elif isinstance(settlement.expense_categories, dict):
                    expense_categories = settlement.expense_categories.copy()
            
            # Check if loan_interest already exists (skip if already added)
            if expense_categories.get("loan_interest"):
                continue
            
            # Add loan interest to expense categories
            expense_categories["loan_interest"] = weekly_interest
            
            # Update settlement
            settlement.expense_categories = expense_categories
            
            # Update total expenses to include interest
            current_expenses = float(settlement.expenses) if settlement.expenses else 0.0
            settlement.expenses = current_expenses + weekly_interest
            
            # Recalculate net profit
            revenue = float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
            settlement.net_profit = revenue - settlement.expenses
            
            updated_count += 1
        
        db.commit()
        print(f"✓ Updated {updated_count} settlements with loan interest")
        
    except Exception as e:
        print(f"✗ Error migrating settlements: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_add_loan_interest()
    print("\n✓ Migration completed successfully!")

