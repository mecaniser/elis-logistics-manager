"""
Trucks router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.truck import Truck
from app.schemas.truck import TruckCreate, TruckResponse, TruckUpdate

router = APIRouter()

@router.get("", response_model=List[TruckResponse])
@router.get("/", response_model=List[TruckResponse])
def get_trucks(
    vehicle_type: Optional[str] = None,  # Filter by 'truck' or 'trailer'
    db: Session = Depends(get_db)
):
    """Get all trucks and trailers, optionally filtered by vehicle_type"""
    query = db.query(Truck)
    if vehicle_type:
        vehicle_type_lower = vehicle_type.lower()
        if vehicle_type_lower in ['truck', 'trailer']:
            query = query.filter(Truck.vehicle_type == vehicle_type_lower)
    return query.order_by(Truck.vehicle_type, Truck.name).all()

@router.post("", response_model=TruckResponse)
@router.post("/", response_model=TruckResponse)
def create_truck(truck: TruckCreate, db: Session = Depends(get_db)):
    """Create a new truck or trailer"""
    # Validate vehicle_type
    vehicle_type = truck.vehicle_type.lower()
    if vehicle_type not in ['truck', 'trailer']:
        raise HTTPException(
            status_code=400,
            detail="vehicle_type must be 'truck' or 'trailer'"
        )
    
    # Validate: trucks should have license_plate, trailers should have tag_number
    if vehicle_type == 'truck' and not truck.license_plate:
        # License plate is optional but recommended for trucks
        pass
    elif vehicle_type == 'trailer' and not truck.tag_number:
        # Tag number is recommended for trailers
        pass
    
    # Check for duplicate name within same vehicle type
    existing = db.query(Truck).filter(
        Truck.name == truck.name,
        Truck.vehicle_type == vehicle_type
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A {vehicle_type} with name '{truck.name}' already exists"
        )
    
    truck_dict = truck.dict()
    truck_dict['vehicle_type'] = vehicle_type  # Ensure lowercase
    db_truck = Truck(**truck_dict)
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

@router.put("/{truck_id}", response_model=TruckResponse)
def update_truck(truck_id: int, truck_update: TruckUpdate, db: Session = Depends(get_db)):
    """Update a truck or trailer"""
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    # Update only provided fields
    update_data = truck_update.model_dump(exclude_unset=True)
    # Ensure vehicle_type is lowercase if provided
    if 'vehicle_type' in update_data:
        update_data['vehicle_type'] = update_data['vehicle_type'].lower()
    
    for field, value in update_data.items():
        setattr(truck, field, value)
    
    db.commit()
    db.refresh(truck)
    return truck

@router.delete("/{truck_id}")
def delete_truck(truck_id: int, db: Session = Depends(get_db)):
    """Delete a truck or trailer"""
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    
    db.delete(truck)
    db.commit()
    return {"message": "Vehicle deleted successfully"}

