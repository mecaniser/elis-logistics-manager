"""
Analytics router
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
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
        "other": 0.0
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
                            expense_categories["other"] += amount_float
                        elif category in expense_categories:
                            expense_categories[category] += amount_float
                        else:
                            expense_categories["other"] += amount_float
                except (ValueError, TypeError):
                    continue
        elif settlement.expenses and float(settlement.expenses) > 0:
            expense_categories["other"] += float(settlement.expenses)
    
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
            "net_profit": float(truck_revenue) - float(truck_expenses) - float(truck_repairs_cost)
        })
    
    return {
        "total_trucks": total_trucks,
        "total_settlements": total_settlements,
        "total_revenue": float(total_revenue),
        "total_expenses": float(total_expenses_sum),
        "net_profit": net_profit,
        "expense_categories": expense_categories,
        "truck_profits": truck_profits
    }

