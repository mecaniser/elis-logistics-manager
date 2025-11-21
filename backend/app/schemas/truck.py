"""
Truck schemas - Also supports trailers
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Literal

class TruckBase(BaseModel):
    name: str
    vehicle_type: Literal["truck", "trailer"] = "truck"
    license_plate: Optional[str] = None  # For trucks
    tag_number: Optional[str] = None  # For trailers
    vin: Optional[str] = None
    license_plate_history: Optional[List[str]] = None
    cash_investment: Optional[float] = None  # Cash invested in vehicle
    loan_amount: Optional[float] = None  # Loan amount (trucks only, null for trailers)
    total_cost: Optional[float] = None  # Total purchase cost (cash + loan for trucks, cash only for trailers)

class TruckCreate(TruckBase):
    pass

class TruckUpdate(BaseModel):
    name: Optional[str] = None
    vehicle_type: Optional[Literal["truck", "trailer"]] = None
    license_plate: Optional[str] = None
    tag_number: Optional[str] = None
    vin: Optional[str] = None
    license_plate_history: Optional[List[str]] = None
    cash_investment: Optional[float] = None
    loan_amount: Optional[float] = None
    total_cost: Optional[float] = None

class TruckResponse(TruckBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

