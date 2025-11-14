"""
Repair schemas
"""
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List
from decimal import Decimal

class RepairBase(BaseModel):
    truck_id: int
    repair_date: date
    description: Optional[str] = None
    category: Optional[str] = None
    cost: Decimal
    receipt_path: Optional[str] = None
    invoice_number: Optional[str] = None
    image_paths: Optional[List[str]] = None

class RepairCreate(RepairBase):
    pass

class RepairUpdate(BaseModel):
    truck_id: Optional[int] = None
    repair_date: Optional[date] = None
    description: Optional[str] = None
    category: Optional[str] = None
    cost: Optional[Decimal] = None

class RepairResponse(RepairBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class RepairUploadResponse(BaseModel):
    repair: RepairResponse
    warning: Optional[str] = None

