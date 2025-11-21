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
    
    # Validate investment fields
    if vehicle_type == 'trailer':
        # Trailers should not have loans
        if truck.loan_amount and truck.loan_amount > 0:
            raise HTTPException(
                status_code=400,
                detail="Trailers cannot have loan amounts. Set loan_amount to 0 or null."
            )
        # For trailers, total_cost should equal cash_investment + registration_fee (if provided)
        if truck.cash_investment is not None and truck.total_cost is not None:
            cash = float(truck.cash_investment)
            total = float(truck.total_cost)
            registration = float(truck.registration_fee) if truck.registration_fee else 0.0
            expected_total = cash + registration
            
            if abs(total - expected_total) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=f"For trailers, total_cost ({total}) must equal cash_investment ({cash}) + registration_fee ({registration})"
                )
    elif vehicle_type == 'truck':
        # For trucks, validate total_cost = cash_investment + loan_amount + registration_fee (if all provided)
        if truck.cash_investment is not None and truck.total_cost is not None:
            cash = float(truck.cash_investment)
            total = float(truck.total_cost)
            loan = float(truck.loan_amount) if truck.loan_amount else 0.0
            registration = float(truck.registration_fee) if truck.registration_fee else 0.0
            
            expected_total = cash + loan + registration
            if abs(total - expected_total) > 0.01:
                raise HTTPException(
                    status_code=400,
                    detail=f"total_cost ({total}) must equal cash_investment ({cash}) + loan_amount ({loan}) + registration_fee ({registration})"
                )
    
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
    
    truck_dict = truck.model_dump()
    truck_dict['vehicle_type'] = vehicle_type  # Ensure lowercase
    # Set default interest_rate if not provided
    if 'interest_rate' not in truck_dict or truck_dict['interest_rate'] is None:
        truck_dict['interest_rate'] = 0.07  # Default 7%
    # Initialize current_loan_balance = loan_amount for trucks
    if vehicle_type == 'truck' and truck_dict.get('loan_amount'):
        if 'current_loan_balance' not in truck_dict or truck_dict['current_loan_balance'] is None:
            truck_dict['current_loan_balance'] = truck_dict['loan_amount']
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
        vehicle_type = update_data['vehicle_type']
    else:
        vehicle_type = truck.vehicle_type
    
    # Validate investment fields if being updated
    if 'loan_amount' in update_data or 'cash_investment' in update_data or 'total_cost' in update_data or 'registration_fee' in update_data:
        cash_investment = update_data.get('cash_investment', truck.cash_investment)
        loan_amount = update_data.get('loan_amount', truck.loan_amount)
        total_cost = update_data.get('total_cost', truck.total_cost)
        registration_fee = update_data.get('registration_fee', truck.registration_fee)
        
        if vehicle_type == 'trailer':
            # Trailers should not have loans
            if loan_amount and float(loan_amount) > 0:
                raise HTTPException(
                    status_code=400,
                    detail="Trailers cannot have loan amounts. Set loan_amount to 0 or null."
                )
            # For trailers, total_cost should equal cash_investment + registration_fee (if provided)
            if cash_investment is not None and total_cost is not None:
                cash = float(cash_investment)
                total = float(total_cost)
                registration = float(registration_fee) if registration_fee else 0.0
                expected_total = cash + registration
                
                if abs(total - expected_total) > 0.01:
                    raise HTTPException(
                        status_code=400,
                        detail=f"For trailers, total_cost ({total}) must equal cash_investment ({cash}) + registration_fee ({registration})"
                    )
        elif vehicle_type == 'truck':
            # For trucks, validate total_cost = cash_investment + loan_amount + registration_fee (if all provided)
            if cash_investment is not None and total_cost is not None:
                cash = float(cash_investment)
                total = float(total_cost)
                loan = float(loan_amount) if loan_amount else 0.0
                registration = float(registration_fee) if registration_fee else 0.0
                
                expected_total = cash + loan + registration
                if abs(total - expected_total) > 0.01:
                    raise HTTPException(
                        status_code=400,
                        detail=f"total_cost ({total}) must equal cash_investment ({cash}) + loan_amount ({loan}) + registration_fee ({registration})"
                    )
    
    # Update current_loan_balance if loan_amount is being updated
    if 'loan_amount' in update_data:
        new_loan_amount = update_data['loan_amount']
        if vehicle_type == 'truck' and new_loan_amount:
            # If loan_amount is updated, reset current_loan_balance to new loan_amount
            # (unless it's being explicitly set in update_data)
            if 'current_loan_balance' not in update_data:
                update_data['current_loan_balance'] = new_loan_amount
        elif vehicle_type == 'trailer':
            # Trailers shouldn't have loan balances
            update_data['current_loan_balance'] = None
    
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

