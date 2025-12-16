"""
Accounting schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class ChartOfAccountBase(BaseModel):
    code: str = Field(..., max_length=20)
    name: str = Field(..., max_length=200)
    account_type: str = Field(..., description="Asset, Liability, Equity, Revenue, Expense")
    parent_id: Optional[int] = None
    truck_id: Optional[int] = None  # For per-asset accounting (LS logistics)
    is_active: bool = True


class ChartOfAccountCreate(ChartOfAccountBase):
    pass


class ChartOfAccountResponse(ChartOfAccountBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class JournalEntryLineBase(BaseModel):
    account_id: int
    debit: float = Field(default=0, ge=0)
    credit: float = Field(default=0, ge=0)
    description: Optional[str] = None
    truck_id: Optional[int] = None


class JournalEntryLineCreate(JournalEntryLineBase):
    pass


class JournalEntryLineResponse(JournalEntryLineBase):
    id: int
    journal_entry_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class JournalEntryBase(BaseModel):
    entry_date: date
    reference_type: Optional[str] = None
    reference_id: Optional[int] = None
    description: Optional[str] = None
    truck_id: Optional[int] = None  # For per-asset accounting (LS logistics)


class JournalEntryCreate(JournalEntryBase):
    lines: List[JournalEntryLineCreate]


class JournalEntryResponse(JournalEntryBase):
    id: int
    created_at: datetime
    lines: List[JournalEntryLineResponse] = []

    class Config:
        from_attributes = True


class GeneralLedgerEntry(BaseModel):
    entry_date: date
    journal_entry_id: int
    account_code: str
    account_name: str
    description: Optional[str]
    debit: float
    credit: float
    running_balance: float


class GeneralLedgerResponse(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: str
    start_balance: float
    end_balance: float
    entries: List[GeneralLedgerEntry]


class BalanceSheetResponse(BaseModel):
    as_of_date: str
    assets: dict
    liabilities: dict
    equity: dict
    total_liabilities_and_equity: float


class IncomeStatementResponse(BaseModel):
    start_date: str
    end_date: str
    truck_id: Optional[int] = None
    revenue: dict
    expenses: dict
    total_expenses: float
    net_income: float

