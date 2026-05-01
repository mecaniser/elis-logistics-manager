"""
Truck schemas - Also supports trailers
"""
from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional, List, Literal, Dict, Any

from app.schemas.vehicle_document import VehicleDocumentResponse

class TruckBase(BaseModel):
    name: str
    vehicle_type: Literal["truck", "trailer", "suv"] = "truck"
    license_plate: Optional[str] = None  # For trucks
    tag_number: Optional[str] = None  # For trailers
    vin: Optional[str] = None
    default_trailer_id: Optional[int] = None
    default_trailer_income_split_amount: Optional[float] = None
    default_repair_reserve_amount: Optional[float] = None
    license_plate_history: Optional[List[str]] = None
    cash_investment: Optional[float] = None  # Cash invested in vehicle
    loan_amount: Optional[float] = None  # Loan amount (trucks only, null for trailers)
    current_loan_balance: Optional[float] = None  # Current loan balance (reduces as principal is paid)
    interest_rate: Optional[float] = 0.07  # Annual interest rate (default 7% = 0.07)
    total_cost: Optional[float] = None  # Total purchase cost (cash + loan for trucks, cash only for trailers)
    registration_fee: Optional[float] = None  # Registration fee for vehicle
    additional_expenses: Optional[List[Dict[str, Any]]] = None  # Additional expenses/fees: [{"description": "...", "amount": 100.00}, ...]
    # Depreciation fields
    purchase_date: Optional[date] = None  # Date vehicle was purchased/placed in service
    depreciation_method: Optional[Literal["MACRS_5", "straight_line", "none"]] = "MACRS_5"
    cost_basis: Optional[float] = None  # Depreciable cost basis (total_cost minus Section 179/bonus depreciation)
    section_179_deduction: Optional[float] = 0  # Section 179 deduction taken in first year
    bonus_depreciation: Optional[float] = 0  # Bonus depreciation percentage (e.g., 100 for 100%)

class TruckCreate(TruckBase):
    pass

class TruckUpdate(BaseModel):
    name: Optional[str] = None
    vehicle_type: Optional[Literal["truck", "trailer", "suv"]] = None
    license_plate: Optional[str] = None
    tag_number: Optional[str] = None
    vin: Optional[str] = None
    default_trailer_id: Optional[int] = None
    default_trailer_income_split_amount: Optional[float] = None
    default_repair_reserve_amount: Optional[float] = None
    license_plate_history: Optional[List[str]] = None
    cash_investment: Optional[float] = None
    loan_amount: Optional[float] = None
    current_loan_balance: Optional[float] = None
    interest_rate: Optional[float] = None
    total_cost: Optional[float] = None
    registration_fee: Optional[float] = None
    purchase_date: Optional[date] = None
    depreciation_method: Optional[Literal["MACRS_5", "straight_line", "none"]] = None
    cost_basis: Optional[float] = None
    section_179_deduction: Optional[float] = None
    bonus_depreciation: Optional[float] = None
    additional_expenses: Optional[List[Dict[str, Any]]] = None

class TruckResponse(TruckBase):
    id: int
    created_at: datetime
    vehicle_documents: Optional[List[VehicleDocumentResponse]] = None

    class Config:
        from_attributes = True
