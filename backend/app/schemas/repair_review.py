"""Owner recollections are evidence, never bank reconciliation or ledger payments."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ReviewItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    repair_id: int
    snapshot: str
    previous_id: str | None = None


class RepairConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    items: list[ReviewItem] = Field(min_length=1, max_length=100)
    status: Literal['paid', 'partial', 'unpaid', 'unknown']
    method: Literal['cash', 'zelle', 'other', 'unknown'] = 'unknown'
    source: Literal['business', 'personal', 'mixed', 'unknown'] = 'unknown'
    paid_amount: Decimal | None = None
    paid_date: date | None = None
    note: str = Field(default='', max_length=1000)

    @field_validator('paid_amount')
    @classmethod
    def valid_amount(cls, value):
        if value is not None and (not value.is_finite() or value <= 0 or value >= Decimal('1000000000000') or value != value.quantize(Decimal('0.01'))):
            raise ValueError('Use a positive amount with at most two decimal places.')
        return value
