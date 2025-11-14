"""
Settlement schemas
"""
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, Dict
from decimal import Decimal

class SettlementBase(BaseModel):
    truck_id: int
    driver_id: Optional[int] = None
    settlement_date: date
    week_start: Optional[date] = None
    week_end: Optional[date] = None
    miles_driven: Optional[Decimal] = None
    blocks_delivered: Optional[int] = None
    gross_revenue: Optional[Decimal] = None
    expenses: Optional[Decimal] = None
    expense_categories: Optional[Dict[str, float]] = None  # Categorized expenses: {fuel, dispatch_fee, insurance, etc}
    net_profit: Optional[Decimal] = None
    license_plate: Optional[str] = None  # License plate from this settlement
    settlement_type: Optional[str] = None  # Type of settlement PDF

class SettlementCreate(SettlementBase):
    pdf_file_path: Optional[str] = None

class SettlementUpdate(BaseModel):
    truck_id: Optional[int] = None
    driver_id: Optional[int] = None
    settlement_date: Optional[date] = None
    week_start: Optional[date] = None
    week_end: Optional[date] = None
    miles_driven: Optional[Decimal] = None
    blocks_delivered: Optional[int] = None
    gross_revenue: Optional[Decimal] = None
    expenses: Optional[Decimal] = None
    expense_categories: Optional[Dict[str, float]] = None
    net_profit: Optional[Decimal] = None
    license_plate: Optional[str] = None
    settlement_type: Optional[str] = None

class SettlementResponse(SettlementBase):
    id: int
    pdf_file_path: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

