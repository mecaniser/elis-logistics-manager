"""
Tenant schemas
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TenantBase(BaseModel):
    name: str
    business_type: str = 'logistics'  # 'logistics', 'tech', 'real_estate', etc.
    is_active: bool = True
    ein: Optional[str] = None
    legal_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    bank_accounts: Optional[list] = None  # List of bank account dicts
    notes: Optional[str] = None

class TenantCreate(TenantBase):
    pass

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    business_type: Optional[str] = None
    is_active: Optional[bool] = None
    ein: Optional[str] = None
    legal_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    bank_accounts: Optional[list] = None
    notes: Optional[str] = None

class TenantResponse(TenantBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

