#!/usr/bin/env python3
"""
Migration script to recalculate loan interest chronologically based on current_loan_balance
and apply principal payments after cash investment recovery.
Works with both SQLite (local) and PostgreSQL (Railway)

This script:
1. Processes settlements chronologically (by date)
2. Calculates interest based on current_loan_balance (not original loan_amount)
3. Tracks principal payments that occur after cash investment is recovered
4. Updates loan balance progressively as principal is paid
5. Recalculates expenses and net_profit for each settlement
"""
import sys
import os
import json
from datetime import datetime

# Add the backend directory to the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from app.database import engine, DATABASE_URL, get_db
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.models.repair import Repair
from app.utils.loan_interest import calculate_weekly_loan_interest, calculate_principal_payment
from sqlalchemy.orm import Session
from sqlalchemy import func

def get_settlement_date(settlement: Settlement) -> datetime:
    """Get the date to use for sorting settlements chronologically"""
    if settlement.week_start:
        return settlement.week_start
    elif settlement.settlement_date:
        return settlement.settlement_date
    else:
        # Fallback to created_at if no date available
        return settlement.created_at if settlement.created_at else datetime.now()

def migrate_recalculate_loan_interest():
    """Recalculate loan interest chronologically with principal payments"""
    
    db: Session = next(get_db())
    
    try:
        # Get all trucks with loans
        trucks = db.query(Truck).filter(
            Truck.vehicle_type == 'truck',
            Truck.loan_amount.isnot(None),
            Truck.loan_amount > 0
        ).all()
        
        total_updated = 0
        
        for truck in trucks:
            print(f"\nProcessing truck: {truck.name} (ID: {truck.id})")
            
            # Initialize current_loan_balance if not set
            if truck.current_loan_balance is None:
                truck.current_loan_balance = truck.loan_amount
                print(f"  Initialized current_loan_balance: ${float(truck.current_loan_balance):,.2f}")
            
            loan_amount = float(truck.loan_amount) if truck.loan_amount else None
            cash_investment = float(truck.cash_investment) if truck.cash_investment else None
            interest_rate = float(truck.interest_rate) if truck.interest_rate else 0.07
            
            if not loan_amount or loan_amount <= 0:
                continue
            
            # Get all settlements for this truck, ordered chronologically
            settlements = db.query(Settlement).filter(
                Settlement.truck_id == truck.id
            ).order_by(
                Settlement.week_start.asc().nullslast(),
                Settlement.settlement_date.asc().nullslast()
            ).all()
            
            if not settlements:
                print(f"  No settlements found for this truck")
                continue
            
            # Track current loan balance as we process settlements
            current_loan_balance = float(truck.current_loan_balance) if truck.current_loan_balance is not None else loan_amount
            cumulative_revenue = 0.0
            cumulative_settlement_expenses = 0.0
            
            # Get all repairs for this truck, ordered by date
            repairs = db.query(Repair).filter(
                Repair.truck_id == truck.id,
                Repair.repair_date.isnot(None)
            ).order_by(Repair.repair_date.asc()).all()
            
            truck_updated_count = 0
            cumulative_repair_costs = 0.0
            repair_index = 0  # Track which repairs we've processed
            
            for settlement in settlements:
                settlement_date = get_settlement_date(settlement)
                
                # Add repair costs up to this settlement date (only count each repair once)
                while repair_index < len(repairs):
                    repair = repairs[repair_index]
                    if repair.repair_date and repair.repair_date <= settlement_date:
                        cumulative_repair_costs += float(repair.cost) if repair.cost else 0.0
                        repair_index += 1
                    else:
                        break  # No more repairs before this settlement date
                
                # Calculate interest based on current loan balance at this point in time
                weekly_interest = calculate_weekly_loan_interest(current_loan_balance, interest_rate)
                
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
                
                # Get old loan interest (if exists) to subtract from expenses
                old_loan_interest = expense_categories.get("loan_interest", 0.0)
                if isinstance(old_loan_interest, str):
                    try:
                        old_loan_interest = float(old_loan_interest)
                    except (ValueError, TypeError):
                        old_loan_interest = 0.0
                else:
                    old_loan_interest = float(old_loan_interest) if old_loan_interest else 0.0
                
                # Update loan interest in expense categories
                expense_categories["loan_interest"] = weekly_interest
                
                # Update total expenses (remove old interest, add new interest)
                current_expenses = float(settlement.expenses) if settlement.expenses else 0.0
                new_expenses = current_expenses - old_loan_interest + weekly_interest
                settlement.expenses = new_expenses
                
                # Recalculate net profit
                revenue = float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
                settlement.net_profit = revenue - new_expenses
                
                # Update cumulative totals
                cumulative_revenue += revenue
                cumulative_settlement_expenses += new_expenses
                
                # Calculate cumulative net profit up to this point
                cumulative_net_profit = cumulative_revenue - cumulative_settlement_expenses - cumulative_repair_costs
                
                # Calculate principal payment and update loan balance
                if cash_investment and cash_investment > 0:
                    principal_payment, new_loan_balance = calculate_principal_payment(
                        cumulative_net_profit,
                        cash_investment,
                        current_loan_balance
                    )
                    
                    if principal_payment > 0:
                        current_loan_balance = new_loan_balance
                        print(f"  Settlement {settlement.id} ({settlement_date.strftime('%Y-%m-%d') if settlement_date else 'N/A'}): "
                              f"Interest: ${weekly_interest:.2f}, Principal paid: ${principal_payment:.2f}, "
                              f"New balance: ${current_loan_balance:.2f}")
                    else:
                        print(f"  Settlement {settlement.id} ({settlement_date.strftime('%Y-%m-%d') if settlement_date else 'N/A'}): "
                              f"Interest: ${weekly_interest:.2f}, Balance: ${current_loan_balance:.2f}")
                else:
                    print(f"  Settlement {settlement.id} ({settlement_date.strftime('%Y-%m-%d') if settlement_date else 'N/A'}): "
                          f"Interest: ${weekly_interest:.2f}, Balance: ${current_loan_balance:.2f}")
                
                settlement.expense_categories = expense_categories
                truck_updated_count += 1
            
            # Update truck's current_loan_balance
            truck.current_loan_balance = current_loan_balance
            print(f"  ✓ Updated {truck_updated_count} settlements, final loan balance: ${current_loan_balance:,.2f}")
            total_updated += truck_updated_count
        
        db.commit()
        print(f"\n✓ Migration completed! Updated {total_updated} settlements across {len(trucks)} trucks")
        
    except Exception as e:
        print(f"✗ Error migrating settlements: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrate_recalculate_loan_interest()
    print("\n✓ Migration completed successfully!")

