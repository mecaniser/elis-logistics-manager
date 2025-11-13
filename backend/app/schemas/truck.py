"""
Truck schemas
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TruckBase(BaseModel):
    name: str
    license_plate: Optional[str] = None

class TruckCreate(TruckBase):
    pass

class TruckResponse(TruckBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

