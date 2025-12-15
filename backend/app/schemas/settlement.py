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
        """Parse block_ids from JSONB/JSON string if needed and validate structure"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return v
        
        # Validate structure if it's a list
        if isinstance(v, list):
            validated = []
            for item in v:
                if isinstance(item, str):
                    validated.append(item)
                elif isinstance(item, dict):
                    # Ensure dict has block_id (required) and optionally delivery_date
                    if 'block_id' in item:
                        validated.append({
                            'block_id': str(item['block_id']),
                            'delivery_date': item.get('delivery_date')  # Optional, keep as-is
                        })
                    else:
                        # If no block_id key, treat as invalid and skip or use the dict as-is
                        validated.append(item)
                else:
                    validated.append(item)
            return validated
        
        return v
    gross_revenue: Optional[Decimal] = None
    expenses: Optional[Decimal] = None
    expense_categories: Optional[Dict[str, float]] = None  # Categorized expenses: {fuel, dispatch_fee, insurance, etc}
    custom_expense_descriptions: Optional[Dict[str, str]] = None  # Descriptions for custom expenses: {custom_1: "handles replaced", custom_2: "truck parking"}
    custom_expense_validation: Optional[Dict[str, bool]] = None  # Validation status for custom expenses: {deduct: true, decals: false, custom: true}
    reimbursement_details: Optional[List[Dict[str, Any]]] = None  # Reimbursement details: [{"description": "...", "amount": 100.00}]
    deduction_details: Optional[List[Dict[str, Any]]] = None  # Deduction details: [{"description": "...", "amount": 50.00}]
    net_profit: Optional[Decimal] = None
    license_plate: Optional[str] = None  # License plate from this settlement
    settlement_type: Optional[str] = None  # Type of settlement PDF
    duplicate_block_ids_warning: Optional[Dict[str, Any]] = None  # Warning about duplicate block IDs

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
    custom_expense_validation: Optional[Dict[str, bool]] = None
    reimbursement_details: Optional[List[Dict[str, Any]]] = None
    deduction_details: Optional[List[Dict[str, Any]]] = None
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

