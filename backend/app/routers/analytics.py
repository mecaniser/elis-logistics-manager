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
def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard summary data"""
    trucks = db.query(Truck).all()
    
    dashboard_data = []
    for truck in trucks:
        settlements_total = db.query(
            func.sum(Settlement.net_profit).label("total")
        ).filter(Settlement.truck_id == truck.id).scalar() or 0
        
        repairs_total = db.query(
            func.sum(Repair.cost).label("total")
        ).filter(Repair.truck_id == truck.id).scalar() or 0
        
        dashboard_data.append({
            "truck_id": truck.id,
            "truck_name": truck.name,
            "settlements_total": float(settlements_total),
            "repairs_total": float(repairs_total),
            "net_profit": float(settlements_total) - float(repairs_total)
        })
    
    return {
        "trucks": dashboard_data,
        "total_profit": sum(t["net_profit"] for t in dashboard_data)
    }

