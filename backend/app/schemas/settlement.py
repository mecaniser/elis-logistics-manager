"""
Settlement schemas
"""
from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Optional, Dict, List, Union, Any
from decimal import Decimal
import json

class BlockIdItem(BaseModel):
    block_id: str
    delivery_date: Optional[str] = None

class SettlementBase(BaseModel):
    truck_id: int
    driver_id: Optional[int] = None
    settlement_date: date
    week_start: Optional[date] = None
    week_end: Optional[date] = None
    miles_driven: Optional[Decimal] = None
    blocks_delivered: Optional[int] = None
    block_ids: Optional[List[Union[str, Dict[str, Any]]]] = None  # Array of block IDs (strings) or objects with block_id and delivery_date
    
    @field_validator('block_ids', mode='before')
    @classmethod
    def parse_block_ids(cls, v):
        """Parse block_ids from JSONB/JSON string if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return v
        return v
    gross_revenue: Optional[Decimal] = None
    expenses: Optional[Decimal] = None
    expense_categories: Optional[Dict[str, float]] = None  # Categorized expenses: {fuel, dispatch_fee, insurance, etc}
    custom_expense_descriptions: Optional[Dict[str, str]] = None  # Descriptions for custom expenses: {custom_1: "handles replaced", custom_2: "truck parking"}
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
    block_ids: Optional[List[Union[str, Dict[str, Any]]]] = None
    gross_revenue: Optional[Decimal] = None
    expenses: Optional[Decimal] = None
    expense_categories: Optional[Dict[str, float]] = None
    custom_expense_descriptions: Optional[Dict[str, str]] = None
    net_profit: Optional[Decimal] = None
    license_plate: Optional[str] = None
    settlement_type: Optional[str] = None
    pdf_file_path: Optional[str] = None

class SettlementResponse(SettlementBase):
    id: int
    pdf_file_path: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

