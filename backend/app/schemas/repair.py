"""
Repair schemas
"""
from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from decimal import Decimal

class RepairBase(BaseModel):
    truck_id: int
    repair_date: date
    description: Optional[str] = None
    category: Optional[str] = None
    cost: Decimal
    receipt_path: Optional[str] = None

class RepairCreate(RepairBase):
    pass

class RepairResponse(RepairBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

