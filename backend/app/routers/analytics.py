"""
Analytics router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.database import get_db
from app.models.settlement import Settlement
from app.models.repair import Repair
from app.models.truck import Truck
from typing import List, Dict, Optional
from datetime import datetime, timedelta, date
from collections import defaultdict

router = APIRouter()

@router.get("/truck-profit/{truck_id}")
def get_truck_profit(truck_id: int, db: Session = Depends(get_db)):
    """Calculate profit per truck (settlements - repairs)"""
    # Get total settlements
    settlements_total = db.query(
        func.sum(Settlement.net_profit).label("total")
    ).filter(Settlement.truck_id == truck_id).scalar() or 0
    
    # Get total repairs
    repairs_total = db.query(
        func.sum(Repair.cost).label("total")
    ).filter(Repair.truck_id == truck_id).scalar() or 0
    
    net_profit = float(settlements_total) - float(repairs_total)
    
    return {
        "truck_id": truck_id,
        "settlements_total": float(settlements_total),
        "repairs_total": float(repairs_total),
        "net_profit": net_profit
    }

@router.get("/vehicle/{truck_id}/roi")
def get_vehicle_roi(truck_id: int, db: Session = Depends(get_db)):
    """Calculate ROI metrics for a specific vehicle (truck or trailer)"""
    # Get the vehicle
    vehicle = db.query(Truck).filter(Truck.id == truck_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Get cumulative net profit (revenue - settlement expenses - repairs)
    vehicle_settlements = db.query(Settlement).filter(Settlement.truck_id == truck_id)
    vehicle_repairs = db.query(Repair).filter(Repair.truck_id == truck_id)
    
    revenue = vehicle_settlements.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
    settlement_expenses = vehicle_settlements.with_entities(func.sum(Settlement.expenses)).scalar() or 0
    repair_costs = vehicle_repairs.with_entities(func.sum(Repair.cost)).scalar() or 0
    
    # Get investment fields
    cash_investment = float(vehicle.cash_investment) if vehicle.cash_investment else None
    loan_amount = float(vehicle.loan_amount) if vehicle.loan_amount else None
    current_loan_balance = float(vehicle.current_loan_balance) if vehicle.current_loan_balance is not None else loan_amount
    interest_rate = float(vehicle.interest_rate) if vehicle.interest_rate else 0.07  # Default 7%
    total_cost = float(vehicle.total_cost) if vehicle.total_cost else None
    registration_fee = float(vehicle.registration_fee) if vehicle.registration_fee else None
    
    # Calculate cumulative loan interest from stored settlement data
    # Interest is stored in expense_categories["loan_interest"] for each settlement
    cumulative_loan_interest = 0.0
    settlements_list = vehicle_settlements.all()
    for settlement in settlements_list:
        if settlement.expense_categories and isinstance(settlement.expense_categories, dict):
            loan_interest = settlement.expense_categories.get("loan_interest", 0)
            if loan_interest:
                cumulative_loan_interest += float(loan_interest)
    
    # Net profit: revenue - settlement expenses (which already includes loan interest) - repairs
    # Note: settlement_expenses already includes loan_interest, so we don't subtract it again
    cumulative_net_profit = float(revenue) - float(settlement_expenses) - float(repair_costs)
    
    # Calculate ROI metrics based on total_cost (which includes cash, loan, and registration)
    investment_recovery_percentage = None
    remaining_to_break_even = None
    break_even_achieved = False
    
    if total_cost and total_cost > 0:
        investment_recovery_percentage = (cumulative_net_profit / total_cost) * 100
        remaining_to_break_even = max(0.0, total_cost - cumulative_net_profit)
        break_even_achieved = cumulative_net_profit >= total_cost
    
    return {
        "vehicle_id": truck_id,
        "vehicle_name": vehicle.name,
        "vehicle_type": vehicle.vehicle_type,
        "cash_investment": cash_investment,
        "loan_amount": loan_amount,
        "current_loan_balance": round(current_loan_balance, 2) if current_loan_balance is not None else None,
        "interest_rate": interest_rate,
        "total_cost": total_cost,
        "registration_fee": registration_fee,
        "cumulative_revenue": float(revenue),
        "cumulative_settlement_expenses": float(settlement_expenses),
        "cumulative_repair_costs": float(repair_costs),
        "cumulative_loan_interest": round(cumulative_loan_interest, 2),
        "cumulative_net_profit": round(cumulative_net_profit, 2),
        "investment_recovery_percentage": round(investment_recovery_percentage, 2) if investment_recovery_percentage is not None else None,
        "remaining_to_break_even": round(remaining_to_break_even, 2) if remaining_to_break_even is not None else None,
        "break_even_achieved": break_even_achieved
    }

@router.get("/dashboard")
def get_dashboard(truck_id: int = None, vehicle_type: Optional[str] = None, db: Session = Depends(get_db)):
    """Get dashboard summary data with expense categories. Separates trucks and trailers."""
    # Build queries with optional truck filter
    trucks_query = db.query(Truck)
    settlements_query = db.query(Settlement)
    repairs_query = db.query(Repair)
    
    if truck_id is not None:
        trucks_query = trucks_query.filter(Truck.id == truck_id)
        settlements_query = settlements_query.filter(Settlement.truck_id == truck_id)
        repairs_query = repairs_query.filter(Repair.truck_id == truck_id)
    
    # Separate trucks and trailers queries
    trucks_only_query = trucks_query.filter(Truck.vehicle_type == 'truck')
    trailers_only_query = trucks_query.filter(Truck.vehicle_type == 'trailer')
    
    # Get truck totals
    truck_ids = [t.id for t in trucks_only_query.all()]
    trailer_ids = [t.id for t in trailers_only_query.all()]
    
    truck_settlements_query = settlements_query.filter(Settlement.truck_id.in_(truck_ids)) if truck_ids else settlements_query.filter(False)
    trailer_settlements_query = settlements_query.filter(Settlement.truck_id.in_(trailer_ids)) if trailer_ids else settlements_query.filter(False)
    
    truck_repairs_query = repairs_query.filter(Repair.truck_id.in_(truck_ids)) if truck_ids else repairs_query.filter(False)
    trailer_repairs_query = repairs_query.filter(Repair.truck_id.in_(trailer_ids)) if trailer_ids else repairs_query.filter(False)
    
    # Get totals for trucks
    total_trucks = trucks_only_query.count()
    truck_settlements_count = truck_settlements_query.count()
    truck_revenue = truck_settlements_query.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
    truck_expenses = truck_settlements_query.with_entities(func.sum(Settlement.expenses)).scalar() or 0
    truck_repairs_cost = truck_repairs_query.with_entities(func.sum(Repair.cost)).scalar() or 0
    
    # Get totals for trailers
    total_trailers = trailers_only_query.count()
    trailer_settlements_count = trailer_settlements_query.count()
    trailer_revenue = trailer_settlements_query.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
    trailer_expenses = trailer_settlements_query.with_entities(func.sum(Settlement.expenses)).scalar() or 0
    trailer_repairs_cost = trailer_repairs_query.with_entities(func.sum(Repair.cost)).scalar() or 0
    
    # Combined totals (for backward compatibility)
    total_settlements = settlements_query.count()
    total_revenue = settlements_query.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
    total_expenses = settlements_query.with_entities(func.sum(Settlement.expenses)).scalar() or 0
    total_repairs_cost = repairs_query.with_entities(func.sum(Repair.cost)).scalar() or 0
    
    # Standard expense categories
    STANDARD_CATEGORIES = [
        "fuel", "dispatch_fee", "insurance", "safety", "prepass", "ifta",
        "driver_pay", "payroll_fee", "loan_interest", "truck_parking", "service_on_truck"
    ]
    
    # Helper function to calculate expense categories for a set of settlements
    def calculate_expense_categories(settlements_list, repairs_list):
        """Calculate expense categories from settlements and repairs"""
        expense_cats = {
            "fuel": 0.0,
            "dispatch_fee": 0.0,
            "insurance": 0.0,
            "safety": 0.0,
            "prepass": 0.0,
            "ifta": 0.0,
            "driver_pay": 0.0,
            "payroll_fee": 0.0,
            "loan_interest": 0.0,
            "truck_parking": 0.0,
            "service_on_truck": 0.0,
            "repairs": 0.0,
            "custom": 0.0
        }
        custom_descs = {}
        
        def extract_custom_description(category_key: str) -> str:
            if category_key.startswith("custom_"):
                desc = category_key.replace("custom_", "")
                return " ".join(word.capitalize() for word in desc.split("_"))
            return "Custom"
        
        # Add expenses from settlements
        for settlement in settlements_list:
            if settlement.expense_categories and isinstance(settlement.expense_categories, dict) and len(settlement.expense_categories) > 0:
                for category, amount in settlement.expense_categories.items():
                    try:
                        amount_float = float(amount) if amount is not None else 0.0
                        if amount_float > 0:
                            if category == "fees" or category == "other":
                                expense_cats["custom"] += amount_float
                            elif category in expense_cats:
                                expense_cats[category] += amount_float
                            elif category.startswith("custom_"):
                                expense_cats["custom"] += amount_float
                                if category not in custom_descs:
                                    custom_descs[category] = extract_custom_description(category)
                            else:
                                expense_cats["custom"] += amount_float
                                if category not in custom_descs:
                                    custom_descs[category] = extract_custom_description(category)
                    except (ValueError, TypeError):
                        continue
            elif settlement.expenses and float(settlement.expenses) > 0:
                expense_cats["custom"] += float(settlement.expenses)
        
        # Add repairs
        for repair in repairs_list:
            if repair.cost:
                expense_cats["repairs"] += float(repair.cost)
        
        return expense_cats, custom_descs
    
    # Calculate expense categories separately for trucks and trailers
    truck_settlements = truck_settlements_query.all()
    trailer_settlements = trailer_settlements_query.all()
    truck_repairs = truck_repairs_query.all()
    trailer_repairs = trailer_repairs_query.all()
    
    truck_expense_categories, truck_custom_descriptions = calculate_expense_categories(truck_settlements, truck_repairs)
    trailer_expense_categories, trailer_custom_descriptions = calculate_expense_categories(trailer_settlements, trailer_repairs)
    
    # Combined expense categories (for backward compatibility)
    expense_categories = {
        "fuel": truck_expense_categories["fuel"] + trailer_expense_categories["fuel"],
        "dispatch_fee": truck_expense_categories["dispatch_fee"] + trailer_expense_categories["dispatch_fee"],
        "insurance": truck_expense_categories["insurance"] + trailer_expense_categories["insurance"],
        "safety": truck_expense_categories["safety"] + trailer_expense_categories["safety"],
        "prepass": truck_expense_categories["prepass"] + trailer_expense_categories["prepass"],
        "ifta": truck_expense_categories["ifta"] + trailer_expense_categories["ifta"],
        "driver_pay": truck_expense_categories["driver_pay"] + trailer_expense_categories["driver_pay"],
        "payroll_fee": truck_expense_categories["payroll_fee"] + trailer_expense_categories["payroll_fee"],
        "loan_interest": truck_expense_categories["loan_interest"] + trailer_expense_categories["loan_interest"],
        "truck_parking": truck_expense_categories["truck_parking"] + trailer_expense_categories["truck_parking"],
        "service_on_truck": truck_expense_categories["service_on_truck"] + trailer_expense_categories["service_on_truck"],
        "repairs": truck_expense_categories["repairs"] + trailer_expense_categories["repairs"],
        "custom": truck_expense_categories["custom"] + trailer_expense_categories["custom"]
    }
    
    # Merge custom descriptions
    custom_descriptions = {**truck_custom_descriptions, **trailer_custom_descriptions}
    
    # Calculate net profits
    truck_expenses_sum = sum(truck_expense_categories.values())
    trailer_expenses_sum = sum(trailer_expense_categories.values())
    truck_net_profit = float(truck_revenue) - float(truck_expenses_sum)
    trailer_net_profit = float(trailer_revenue) - float(trailer_expenses_sum)
    
    # Combined net profit (for backward compatibility)
    total_expenses_sum = sum(expense_categories.values())
    net_profit = float(total_revenue) - float(total_expenses_sum)
    
    # Get truck profits (only trucks, not trailers)
    truck_profits = []
    trucks = trucks_only_query.all()
    for truck in trucks:
        truck_settlements = db.query(Settlement).filter(Settlement.truck_id == truck.id)
        truck_repairs = db.query(Repair).filter(Repair.truck_id == truck.id)
        
        truck_revenue = truck_settlements.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
        truck_expenses = truck_settlements.with_entities(func.sum(Settlement.expenses)).scalar() or 0
        truck_repairs_cost = truck_repairs.with_entities(func.sum(Repair.cost)).scalar() or 0
        
        # Calculate profit before repairs (revenue - settlement expenses only)
        profit_before_repairs = float(truck_revenue) - float(truck_expenses)
        
        truck_profits.append({
            "truck_id": truck.id,
            "truck_name": truck.name,
            "license_plate": truck.license_plate,
            "vin": truck.vin,
            "total_revenue": float(truck_revenue),
            "total_expenses": float(truck_expenses) + float(truck_repairs_cost),
            "settlement_expenses": float(truck_expenses),
            "repair_costs": float(truck_repairs_cost),
            "profit_before_repairs": profit_before_repairs,
            "net_profit": float(truck_revenue) - float(truck_expenses) - float(truck_repairs_cost)
        })
    
    # Get trailer profits
    trailer_profits = []
    trailers = trailers_only_query.all()
    for trailer in trailers:
        trailer_settlements = db.query(Settlement).filter(Settlement.truck_id == trailer.id)
        trailer_repairs = db.query(Repair).filter(Repair.truck_id == trailer.id)
        
        trailer_revenue = trailer_settlements.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
        trailer_expenses = trailer_settlements.with_entities(func.sum(Settlement.expenses)).scalar() or 0
        trailer_repairs_cost = trailer_repairs.with_entities(func.sum(Repair.cost)).scalar() or 0
        
        # Calculate profit before repairs (revenue - settlement expenses only)
        profit_before_repairs = float(trailer_revenue) - float(trailer_expenses)
        
        trailer_profits.append({
            "truck_id": trailer.id,
            "truck_name": trailer.name,
            "tag_number": trailer.tag_number,
            "vin": trailer.vin,
            "total_revenue": float(trailer_revenue),
            "total_expenses": float(trailer_expenses) + float(trailer_repairs_cost),
            "settlement_expenses": float(trailer_expenses),
            "repair_costs": float(trailer_repairs_cost),
            "profit_before_repairs": profit_before_repairs,
            "net_profit": float(trailer_revenue) - float(trailer_expenses) - float(trailer_repairs_cost)
        })
    
    # Get blocks by truck and month
    blocks_by_truck_month = []
    trucks_for_blocks = trucks_query.all()
    
    for truck in trucks_for_blocks:
        truck_settlements = db.query(Settlement).filter(Settlement.truck_id == truck.id)
        if truck_id is not None:
            # Already filtered above
            pass
        
        # Group settlements by month based on week_start if available, otherwise settlement_date
        # Apply 28th cutoff: if week_start is >= 28th, count in next month
        # If week_start is in previous month, count in that month (not settlement_date month)
        settlements_by_month = {}
        for settlement in truck_settlements.all():
            if settlement.blocks_delivered:
                date_to_use = None
                
                if settlement.week_start:
                    # Use week_start to determine month
                    # If week_start is >= 28th, move to next month
                    if settlement.week_start.day >= 28:
                        if settlement.week_start.month == 12:
                            date_to_use = settlement.week_start.replace(year=settlement.week_start.year + 1, month=1, day=1)
                        else:
                            date_to_use = settlement.week_start.replace(month=settlement.week_start.month + 1, day=1)
                    else:
                        # Use week_start's actual month
                        date_to_use = settlement.week_start
                elif settlement.settlement_date:
                    # Fallback to settlement_date if week_start not available
                    # Apply same 28th cutoff
                    if settlement.settlement_date.day >= 28:
                        if settlement.settlement_date.month == 12:
                            date_to_use = settlement.settlement_date.replace(year=settlement.settlement_date.year + 1, month=1, day=1)
                        else:
                            date_to_use = settlement.settlement_date.replace(month=settlement.settlement_date.month + 1, day=1)
                    else:
                        date_to_use = settlement.settlement_date
                
                if date_to_use:
                    month_key = date_to_use.strftime("%Y-%m")
                    month_label = date_to_use.strftime("%b %Y")
                    
                    # Filter out future months (beyond current date)
                    current_date = date.today()
                    month_date = date_to_use.replace(day=1) if date_to_use else None
                    if month_date and month_date > current_date.replace(day=1):
                        continue  # Skip future months
                    
                    if month_key not in settlements_by_month:
                        settlements_by_month[month_key] = {
                            "month": month_label,
                            "month_key": month_key,
                            "blocks": 0
                        }
                    
                    settlements_by_month[month_key]["blocks"] += int(settlement.blocks_delivered) if settlement.blocks_delivered else 0
        
        # Convert to list and sort by month
        for month_key in sorted(settlements_by_month.keys()):
            blocks_by_truck_month.append({
                "truck_id": truck.id,
                "truck_name": truck.name,
                "month": settlements_by_month[month_key]["month"],
                "month_key": settlements_by_month[month_key]["month_key"],
                "blocks": settlements_by_month[month_key]["blocks"]
            })
    
    # Get individual repairs by month (each repair separate)
    repairs_by_month = []
    repairs_for_monthly = repairs_query.all()
    
    # Get truck names for reference
    truck_map = {truck.id: truck.name for truck in trucks_query.all()}
    
    # Create list of individual repairs with month info
    for repair in repairs_for_monthly:
        if repair.repair_date and repair.cost:
            month_key = repair.repair_date.strftime("%Y-%m")
            month_label = repair.repair_date.strftime("%b %Y")
            
            repairs_by_month.append({
                "repair_id": repair.id,
                "month": month_label,
                "month_key": month_key,
                "cost": float(repair.cost),
                "truck_id": repair.truck_id,
                "truck_name": truck_map.get(repair.truck_id, f"Truck {repair.truck_id}"),
                "description": repair.description or "No description",
                "category": repair.category or "other",
                "repair_date": repair.repair_date.isoformat() if repair.repair_date else None
            })
    
    # Sort by month_key and repair_date
    repairs_by_month.sort(key=lambda x: (x["month_key"], x["repair_date"] or ""))
    
    # Get PM (D13 full pm) status for each truck (exclude trailers)
    pm_status = []
    trucks_for_pm = trucks_query.filter(Truck.vehicle_type == 'truck').all()  # Only trucks, not trailers
    today = datetime.now().date()
    pm_threshold_months = 3
    
    for truck in trucks_for_pm:
        # Find all D13 full pm repairs for this truck
        # Search for "d13" and "full pm" in description (case-insensitive)
        # Both terms must be present in the description
        pm_repairs = db.query(Repair).filter(
            and_(
                Repair.truck_id == truck.id,
                Repair.description.ilike('%d13%'),
                Repair.description.ilike('%full pm%')
            )
        ).order_by(Repair.repair_date.desc()).all()
        
        last_pm_date = None
        last_pm_repair_id = None
        if pm_repairs:
            last_pm_repair = pm_repairs[0]  # Most recent
            last_pm_date = last_pm_repair.repair_date
            last_pm_repair_id = last_pm_repair.id
        
        # Calculate if due for PM
        is_due = False
        days_since_pm = None
        days_overdue = None
        
        if last_pm_date:
            days_since_pm = (today - last_pm_date).days
            # PM is due every 3 months (approximately 90 days)
            days_threshold = pm_threshold_months * 30
            is_due = days_since_pm >= days_threshold
            if is_due:
                days_overdue = days_since_pm - days_threshold
        else:
            # No PM found - truck is overdue
            is_due = True
            days_overdue = None
        
        pm_status.append({
            "truck_id": truck.id,
            "truck_name": truck.name,
            "last_pm_date": last_pm_date.isoformat() if last_pm_date else None,
            "last_pm_repair_id": last_pm_repair_id,
            "is_due": is_due,
            "days_since_pm": days_since_pm,
            "days_overdue": days_overdue,
            "pm_threshold_months": pm_threshold_months
        })
    
    return {
        # Combined totals (for backward compatibility)
        "total_trucks": total_trucks,
        "total_settlements": total_settlements,
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses_sum),
        "net_profit": net_profit,
        "expense_categories": expense_categories,
        "custom_descriptions": custom_descriptions,
        "truck_profits": truck_profits,
        "blocks_by_truck_month": blocks_by_truck_month,
        "repairs_by_month": repairs_by_month,
        "pm_status": pm_status,
        # Separated truck data
        "trucks": {
            "total_trucks": total_trucks,
            "total_settlements": truck_settlements_count,
            "total_revenue": float(truck_revenue),
            "total_expenses": float(truck_expenses_sum),
            "net_profit": truck_net_profit,
            "expense_categories": truck_expense_categories,
            "custom_descriptions": truck_custom_descriptions,
            "truck_profits": truck_profits
        },
        # Separated trailer data
        "trailers": {
            "total_trailers": total_trailers,
            "total_settlements": trailer_settlements_count,
            "total_revenue": float(trailer_revenue),
            "total_expenses": float(trailer_expenses_sum),
            "net_profit": trailer_net_profit,
            "expense_categories": trailer_expense_categories,
            "custom_descriptions": trailer_custom_descriptions,
            "trailer_profits": trailer_profits
        }
    }

@router.get("/time-series")
def get_time_series(
    group_by: Optional[str] = "week_start",
    truck_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get time-series data grouped by week and month.
    
    Args:
        group_by: How to group weekly data - "week_start" or "settlement_date" (default: "week_start")
        truck_id: Optional truck filter
    """
    # Validate group_by parameter
    if group_by not in ["week_start", "settlement_date"]:
        group_by = "week_start"
    
    # Build query with optional truck filter
    settlements_query = db.query(Settlement)
    if truck_id is not None:
        settlements_query = settlements_query.filter(Settlement.truck_id == truck_id)
    
    settlements = settlements_query.order_by(Settlement.settlement_date).all()
    
    # Get truck names for reference
    trucks = db.query(Truck).all()
    truck_map = {truck.id: truck.name for truck in trucks}
    
    # Helper function to extract description from custom category key
    def extract_custom_description(category_key: str) -> str:
        """Extract description from custom category key (e.g., 'custom_truck_parking' -> 'Truck Parking')"""
        if category_key.startswith("custom_"):
            desc = category_key.replace("custom_", "")
            # Convert snake_case to Title Case
            return " ".join(word.capitalize() for word in desc.split("_"))
        return "Custom"
    
    # Standard expense categories
    STANDARD_CATEGORIES = ["fuel", "dispatch_fee", "insurance", "safety", "prepass", "ifta", "truck_parking", "driver_pay", "payroll_fee", "loan_interest"]
    
    # Initialize data structures
    weekly_data = defaultdict(lambda: {
        "gross_revenue": 0.0,
        "net_profit": 0.0,
        "driver_pay": 0.0,
        "payroll_fee": 0.0,
        "fuel": 0.0,
        "dispatch_fee": 0.0,
        "insurance": 0.0,
        "safety": 0.0,
        "prepass": 0.0,
        "ifta": 0.0,
        "loan_interest": 0.0,
        "truck_parking": 0.0,
        "custom": 0.0,
        "trucks": set(),
        "week_start": None,
        "week_end": None,
        "settlement_date": None,
        "custom_descriptions": {}  # Track custom category descriptions for this period
    })
    
    monthly_data = defaultdict(lambda: {
        "gross_revenue": 0.0,
        "net_profit": 0.0,
        "driver_pay": 0.0,
        "payroll_fee": 0.0,
        "fuel": 0.0,
        "dispatch_fee": 0.0,
        "insurance": 0.0,
        "safety": 0.0,
        "prepass": 0.0,
        "ifta": 0.0,
        "loan_interest": 0.0,
        "truck_parking": 0.0,
        "custom": 0.0,
        "repairs": 0.0,
        "trucks": set(),
        "custom_descriptions": {}  # Track custom category descriptions for this period
    })
    
    yearly_data = defaultdict(lambda: {
        "gross_revenue": 0.0,
        "net_profit": 0.0,
        "driver_pay": 0.0,
        "payroll_fee": 0.0,
        "fuel": 0.0,
        "dispatch_fee": 0.0,
        "insurance": 0.0,
        "safety": 0.0,
        "prepass": 0.0,
        "ifta": 0.0,
        "loan_interest": 0.0,
        "truck_parking": 0.0,
        "custom": 0.0,
        "repairs": 0.0,
        "trucks": set(),
        "custom_descriptions": {}  # Track custom category descriptions for this period
    })
    
    # Process each settlement
    for settlement in settlements:
        # Determine week key based on group_by parameter
        # When grouping by "week_start", we actually group by settlement_date (pay period end date)
        # because settlements with the same pay period should be grouped together,
        # even if their week_start dates differ slightly
        if group_by == "week_start":
            # Use settlement_date as the key to group by pay period
            week_key = settlement.settlement_date.isoformat()
            # Use week_start/week_end from the settlement if available, otherwise use settlement_date
            week_start = settlement.week_start if settlement.week_start else settlement.settlement_date
            week_end = settlement.week_end if settlement.week_end else settlement.settlement_date
        else:
            # When grouping by settlement_date, use settlement_date as key
            week_key = settlement.settlement_date.isoformat()
            week_start = settlement.week_start if settlement.week_start else settlement.settlement_date
            week_end = settlement.week_end if settlement.week_end else settlement.settlement_date
        
        # Determine month key (using existing logic with 28th cutoff)
        date_to_use = None
        if settlement.week_start:
            if settlement.week_start.day >= 28:
                if settlement.week_start.month == 12:
                    date_to_use = settlement.week_start.replace(year=settlement.week_start.year + 1, month=1, day=1)
                else:
                    date_to_use = settlement.week_start.replace(month=settlement.week_start.month + 1, day=1)
            else:
                date_to_use = settlement.week_start
        elif settlement.settlement_date:
            if settlement.settlement_date.day >= 28:
                if settlement.settlement_date.month == 12:
                    date_to_use = settlement.settlement_date.replace(year=settlement.settlement_date.year + 1, month=1, day=1)
                else:
                    date_to_use = settlement.settlement_date.replace(month=settlement.settlement_date.month + 1, day=1)
            else:
                date_to_use = settlement.settlement_date
        
        month_key = date_to_use.strftime("%Y-%m") if date_to_use else None
        
        # Determine year key
        year_key = None
        if date_to_use:
            year_key = date_to_use.strftime("%Y")
        elif settlement.settlement_date:
            year_key = settlement.settlement_date.strftime("%Y")
        
        # Aggregate weekly data
        weekly_data[week_key]["gross_revenue"] += float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
        weekly_data[week_key]["net_profit"] += float(settlement.net_profit) if settlement.net_profit else 0.0
        weekly_data[week_key]["trucks"].add(settlement.truck_id)
        if not weekly_data[week_key]["week_start"]:
            weekly_data[week_key]["week_start"] = week_start
        if not weekly_data[week_key]["week_end"]:
            weekly_data[week_key]["week_end"] = week_end
        if not weekly_data[week_key]["settlement_date"]:
            weekly_data[week_key]["settlement_date"] = settlement.settlement_date
        
        # Aggregate monthly data
        if month_key:
            monthly_data[month_key]["gross_revenue"] += float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
            monthly_data[month_key]["net_profit"] += float(settlement.net_profit) if settlement.net_profit else 0.0
            monthly_data[month_key]["trucks"].add(settlement.truck_id)
        
        # Aggregate yearly data
        if year_key:
            yearly_data[year_key]["gross_revenue"] += float(settlement.gross_revenue) if settlement.gross_revenue else 0.0
            yearly_data[year_key]["net_profit"] += float(settlement.net_profit) if settlement.net_profit else 0.0
            yearly_data[year_key]["trucks"].add(settlement.truck_id)
        
        # Process expense categories
        if settlement.expense_categories and isinstance(settlement.expense_categories, dict):
            for category, amount in settlement.expense_categories.items():
                try:
                    amount_float = float(amount) if amount is not None else 0.0
                    if amount_float > 0:
                        # Map category names
                        mapped_category = category
                        if category == "fees" or category == "other":
                            mapped_category = "custom"
                        elif category.startswith("custom_") or (category not in STANDARD_CATEGORIES and category != "custom"):
                            # Custom category - aggregate into "custom" and track description
                            mapped_category = "custom"
                            # Track custom description for this period
                            if category not in weekly_data[week_key]["custom_descriptions"]:
                                weekly_data[week_key]["custom_descriptions"][category] = extract_custom_description(category)
                            if month_key and category not in monthly_data[month_key]["custom_descriptions"]:
                                monthly_data[month_key]["custom_descriptions"][category] = extract_custom_description(category)
                            if year_key and category not in yearly_data[year_key]["custom_descriptions"]:
                                yearly_data[year_key]["custom_descriptions"][category] = extract_custom_description(category)
                        
                        if mapped_category in weekly_data[week_key]:
                            weekly_data[week_key][mapped_category] += amount_float
                        
                        if month_key and mapped_category in monthly_data[month_key]:
                            monthly_data[month_key][mapped_category] += amount_float
                        
                        if year_key and mapped_category in yearly_data[year_key]:
                            yearly_data[year_key][mapped_category] += amount_float
                except (ValueError, TypeError):
                    continue
    
    # Format weekly data
    # Filter out future weeks (only show weeks up to current date)
    current_date = datetime.now().date()
    
    by_week = []
    for week_key in sorted(weekly_data.keys()):
        week_data = weekly_data[week_key]
        week_start_date = week_data["week_start"]
        week_end_date = week_data["week_end"]
        settlement_date = week_data["settlement_date"]
        
        # Skip future weeks - check if week_start or settlement_date is in the future
        date_to_check = week_start_date or settlement_date
        if date_to_check and date_to_check > current_date:
            continue
        
        # Format week label
        if week_start_date and week_end_date and week_start_date != week_end_date:
            week_label = f"{week_start_date.strftime('%b %d')}-{week_end_date.strftime('%d, %Y')}"
        elif week_start_date:
            week_label = week_start_date.strftime('%b %d, %Y')
        elif settlement_date:
            week_label = settlement_date.strftime('%b %d, %Y')
        else:
            week_label = week_key
        
        truck_list = [
            {
                "truck_id": tid,
                "truck_name": truck_map.get(tid, f"Truck {tid}")
            }
            for tid in sorted(week_data["trucks"])
        ]
        
        # Convert custom_descriptions dict to format expected by frontend
        custom_descriptions_formatted = {}
        for key, desc in week_data["custom_descriptions"].items():
            custom_descriptions_formatted[key] = desc
        
        by_week.append({
            "week_key": week_key,
            "week_label": week_label,
            "gross_revenue": round(week_data["gross_revenue"], 2),
            "net_profit": round(week_data["net_profit"], 2),
            "driver_pay": round(week_data["driver_pay"], 2),
            "payroll_fee": round(week_data["payroll_fee"], 2),
            "fuel": round(week_data["fuel"], 2),
            "dispatch_fee": round(week_data["dispatch_fee"], 2),
            "insurance": round(week_data["insurance"], 2),
            "safety": round(week_data["safety"], 2),
            "prepass": round(week_data["prepass"], 2),
            "ifta": round(week_data["ifta"], 2),
            "loan_interest": round(week_data["loan_interest"], 2),
            "truck_parking": round(week_data["truck_parking"], 2),
            "custom": round(week_data["custom"], 2),
            "custom_descriptions": custom_descriptions_formatted,
            "trucks": truck_list
        })
    
    # Format monthly data
    # Filter out future months (only show months up to current month)
    current_date = datetime.now().date()
    current_month_key = current_date.strftime("%Y-%m")
    
    # Build a map of which settlements contribute to each month for debugging
    month_settlements_map = defaultdict(list)
    for settlement in settlements:
        # Recalculate month_key for this settlement to match what we used above
        date_to_use = None
        if settlement.week_start:
            if settlement.week_start.day >= 28:
                if settlement.week_start.month == 12:
                    date_to_use = settlement.week_start.replace(year=settlement.week_start.year + 1, month=1, day=1)
                else:
                    date_to_use = settlement.week_start.replace(month=settlement.week_start.month + 1, day=1)
            else:
                date_to_use = settlement.week_start
        elif settlement.settlement_date:
            if settlement.settlement_date.day >= 28:
                if settlement.settlement_date.month == 12:
                    date_to_use = settlement.settlement_date.replace(year=settlement.settlement_date.year + 1, month=1, day=1)
                else:
                    date_to_use = settlement.settlement_date.replace(month=settlement.settlement_date.month + 1, day=1)
            else:
                date_to_use = settlement.settlement_date
        
        if date_to_use:
            month_key = date_to_use.strftime("%Y-%m")
            month_settlements_map[month_key].append({
                "settlement_id": settlement.id,
                "settlement_date": settlement.settlement_date.isoformat() if settlement.settlement_date else None,
                "week_start": settlement.week_start.isoformat() if settlement.week_start else None,
                "truck_id": settlement.truck_id,
                "truck_name": truck_map.get(settlement.truck_id, f"Truck {settlement.truck_id}"),
                "insurance": float(settlement.expense_categories.get("insurance", 0)) if settlement.expense_categories and isinstance(settlement.expense_categories, dict) else 0.0,
                "driver_pay": float(settlement.expense_categories.get("driver_pay", 0)) if settlement.expense_categories and isinstance(settlement.expense_categories, dict) else 0.0,
            })
    
    by_month = []
    for month_key in sorted(monthly_data.keys()):
        # Skip future months
        if month_key > current_month_key:
            continue
            
        month_data = monthly_data[month_key]
        month_date = datetime.strptime(month_key, "%Y-%m")
        month_label = month_date.strftime("%b %Y")
        
        truck_list = [
            {
                "truck_id": tid,
                "truck_name": truck_map.get(tid, f"Truck {tid}")
            }
            for tid in sorted(month_data["trucks"])
        ]
        
        # Convert custom_descriptions dict to format expected by frontend
        custom_descriptions_formatted = {}
        for key, desc in month_data["custom_descriptions"].items():
            custom_descriptions_formatted[key] = desc
        
        by_month.append({
            "month_key": month_key,
            "month_label": month_label,
            "gross_revenue": round(month_data["gross_revenue"], 2),
            "net_profit": round(month_data["net_profit"], 2),
            "driver_pay": round(month_data["driver_pay"], 2),
            "payroll_fee": round(month_data["payroll_fee"], 2),
            "fuel": round(month_data["fuel"], 2),
            "dispatch_fee": round(month_data["dispatch_fee"], 2),
            "insurance": round(month_data["insurance"], 2),
            "safety": round(month_data["safety"], 2),
            "prepass": round(month_data["prepass"], 2),
            "ifta": round(month_data["ifta"], 2),
            "loan_interest": round(month_data["loan_interest"], 2),
            "truck_parking": round(month_data["truck_parking"], 2),
            "custom": round(month_data["custom"], 2),
            "custom_descriptions": custom_descriptions_formatted,
            "trucks": truck_list,
            "settlement_count": len(month_settlements_map.get(month_key, [])),
            "settlements": month_settlements_map.get(month_key, [])  # Include settlement details for debugging
        })
    
    # Add repairs to yearly/monthly data and subtract from net profit
    repairs_query = db.query(Repair)
    if truck_id is not None:
        repairs_query = repairs_query.filter(Repair.truck_id == truck_id)
    
    repairs = repairs_query.all()
    for repair in repairs:
        if repair.cost and repair.repair_date:
            repair_year = repair.repair_date.strftime("%Y")
            if repair_year in yearly_data:
                yearly_data[repair_year]["repairs"] += float(repair.cost)
                # Subtract repairs from net profit to match dashboard calculation
                yearly_data[repair_year]["net_profit"] -= float(repair.cost)
            
            # Also add to monthly if needed (for consistency)
            repair_month = repair.repair_date.strftime("%Y-%m")
            if repair_month in monthly_data:
                monthly_data[repair_month]["repairs"] += float(repair.cost)
                monthly_data[repair_month]["net_profit"] -= float(repair.cost)
    
    # Format yearly data
    # Filter out future years (only show years up to current year)
    current_year = datetime.now().year
    
    by_year = []
    for year_key in sorted(yearly_data.keys()):
        year_int = int(year_key)
        # Skip future years
        if year_int > current_year:
            continue
        
        year_data = yearly_data[year_key]
        year_label = year_key  # e.g., "2025"
        
        truck_list = [
            {
                "truck_id": tid,
                "truck_name": truck_map.get(tid, f"Truck {tid}")
            }
            for tid in sorted(year_data["trucks"])
        ]
        
        # Convert custom_descriptions dict to format expected by frontend
        custom_descriptions_formatted = {}
        for key, desc in year_data["custom_descriptions"].items():
            custom_descriptions_formatted[key] = desc
        
        by_year.append({
            "year_key": year_key,
            "year_label": year_label,
            "gross_revenue": round(year_data["gross_revenue"], 2),
            "net_profit": round(year_data["net_profit"], 2),
            "driver_pay": round(year_data["driver_pay"], 2),
            "payroll_fee": round(year_data["payroll_fee"], 2),
            "fuel": round(year_data["fuel"], 2),
            "dispatch_fee": round(year_data["dispatch_fee"], 2),
            "insurance": round(year_data["insurance"], 2),
            "safety": round(year_data["safety"], 2),
            "prepass": round(year_data["prepass"], 2),
            "ifta": round(year_data["ifta"], 2),
            "loan_interest": round(year_data["loan_interest"], 2),
            "truck_parking": round(year_data["truck_parking"], 2),
            "custom": round(year_data["custom"], 2),
            "custom_descriptions": custom_descriptions_formatted,
            "repairs": round(year_data.get("repairs", 0.0), 2),
            "trucks": truck_list
        })
    
    return {
        "by_week": by_week,
        "by_month": by_month,
        "by_year": by_year
    }

