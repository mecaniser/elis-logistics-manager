"""
Trucks router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.truck import Truck
from app.schemas.truck import TruckCreate, TruckResponse

router = APIRouter()

@router.get("/", response_model=List[TruckResponse])
def get_trucks(db: Session = Depends(get_db)):
    """Get all trucks"""
    return db.query(Truck).all()

@router.post("/", response_model=TruckResponse)
def create_truck(truck: TruckCreate, db: Session = Depends(get_db)):
    """Create a new truck"""
    db_truck = Truck(**truck.dict())
    db.add(db_truck)
    db.commit()
    db.refresh(db_truck)
    return db_truck

@router.get("/{truck_id}", response_model=TruckResponse)
def get_truck(truck_id: int, db: Session = Depends(get_db)):
    """Get a specific truck"""
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    return truck

