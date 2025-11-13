"""
Repairs router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.repair import Repair
from app.schemas.repair import RepairCreate, RepairResponse

router = APIRouter()

@router.get("/", response_model=List[RepairResponse])
def get_repairs(
    truck_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get all repairs, optionally filtered by truck"""
    query = db.query(Repair)
    if truck_id:
        query = query.filter(Repair.truck_id == truck_id)
    return query.order_by(Repair.repair_date.desc()).all()

@router.post("/", response_model=RepairResponse)
def create_repair(repair: RepairCreate, db: Session = Depends(get_db)):
    """Create a new repair expense"""
    db_repair = Repair(**repair.dict())
    db.add(db_repair)
    db.commit()
    db.refresh(db_repair)
    return db_repair

@router.get("/{repair_id}", response_model=RepairResponse)
def get_repair(repair_id: int, db: Session = Depends(get_db)):
    """Get a specific repair"""
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    return repair

@router.delete("/{repair_id}")
def delete_repair(repair_id: int, db: Session = Depends(get_db)):
    """Delete a repair"""
    repair = db.query(Repair).filter(Repair.id == repair_id).first()
    if not repair:
        raise HTTPException(status_code=404, detail="Repair not found")
    db.delete(repair)
    db.commit()
    return {"message": "Repair deleted successfully"}

