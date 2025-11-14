"""
Truck schemas
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class TruckBase(BaseModel):
    name: str
    license_plate: Optional[str] = None
    vin: Optional[str] = None
    license_plate_history: Optional[List[str]] = None

class TruckCreate(TruckBase):
    pass

class TruckResponse(TruckBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

