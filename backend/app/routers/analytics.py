"""
Analytics router
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.database import get_db
from app.models.settlement import Settlement
from app.models.repair import Repair
from app.models.truck import Truck
from typing import List, Dict
from datetime import datetime, timedelta

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

@router.get("/dashboard")
def get_dashboard(truck_id: int = None, db: Session = Depends(get_db)):
    """Get dashboard summary data with expense categories"""
    # Build queries with optional truck filter
    trucks_query = db.query(Truck)
    settlements_query = db.query(Settlement)
    repairs_query = db.query(Repair)
    
    if truck_id is not None:
        trucks_query = trucks_query.filter(Truck.id == truck_id)
        settlements_query = settlements_query.filter(Settlement.truck_id == truck_id)
        repairs_query = repairs_query.filter(Repair.truck_id == truck_id)
    
    # Get totals
    total_trucks = trucks_query.count()
    total_settlements = settlements_query.count()
    total_revenue = settlements_query.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
    total_expenses = settlements_query.with_entities(func.sum(Settlement.expenses)).scalar() or 0
    total_repairs_cost = repairs_query.with_entities(func.sum(Repair.cost)).scalar() or 0
    
    # Combine expenses from settlements and repairs by category
    expense_categories = {
        "fuel": 0.0,
        "dispatch_fee": 0.0,
        "insurance": 0.0,
        "safety": 0.0,
        "prepass": 0.0,
        "ifta": 0.0,
        "driver_pay": 0.0,
        "payroll_fee": 0.0,
               "truck_parking": 0.0,
               "repairs": 0.0,
               "custom": 0.0
           }
    
    # Add expenses from settlements (already categorized)
    settlements = settlements_query.all()
    for settlement in settlements:
        if settlement.expense_categories and isinstance(settlement.expense_categories, dict) and len(settlement.expense_categories) > 0:
            for category, amount in settlement.expense_categories.items():
                try:
                    amount_float = float(amount) if amount is not None else 0.0
                    if amount_float > 0:
                           if category == "fees":
                               expense_categories["custom"] += amount_float
                           elif category in expense_categories:
                               expense_categories[category] += amount_float
                           elif category == "other":
                               # Backward compatibility: map old "other" to "custom"
                               expense_categories["custom"] += amount_float
                           else:
                               expense_categories["custom"] += amount_float
                except (ValueError, TypeError):
                    continue
        elif settlement.expenses and float(settlement.expenses) > 0:
            expense_categories["custom"] += float(settlement.expenses)
    
    # Add all repairs to the "repairs" category
    repairs = repairs_query.all()
    for repair in repairs:
        if repair.cost:
            expense_categories["repairs"] += float(repair.cost)
    
    # Calculate net profit
    total_expenses_sum = sum(expense_categories.values())
    net_profit = float(total_revenue) - float(total_expenses_sum)
    
    # Get truck profits
    truck_profits = []
    trucks = trucks_query.all()
    for truck in trucks:
        truck_settlements = db.query(Settlement).filter(Settlement.truck_id == truck.id)
        truck_repairs = db.query(Repair).filter(Repair.truck_id == truck.id)
        
        truck_revenue = truck_settlements.with_entities(func.sum(Settlement.gross_revenue)).scalar() or 0
        truck_expenses = truck_settlements.with_entities(func.sum(Settlement.expenses)).scalar() or 0
        truck_repairs_cost = truck_repairs.with_entities(func.sum(Repair.cost)).scalar() or 0
        
        truck_profits.append({
            "truck_id": truck.id,
            "truck_name": truck.name,
            "total_revenue": float(truck_revenue),
            "total_expenses": float(truck_expenses) + float(truck_repairs_cost),
            "repair_costs": float(truck_repairs_cost),
            "net_profit": float(truck_revenue) - float(truck_expenses) - float(truck_repairs_cost)
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
    
    # Get PM (D13 full pm) status for each truck
    pm_status = []
    trucks_for_pm = trucks_query.all()
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
        "total_trucks": total_trucks,
        "total_settlements": total_settlements,
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses_sum),
        "net_profit": net_profit,
        "expense_categories": expense_categories,
        "truck_profits": truck_profits,
        "blocks_by_truck_month": blocks_by_truck_month,
        "repairs_by_month": repairs_by_month,
        "pm_status": pm_status
    }

