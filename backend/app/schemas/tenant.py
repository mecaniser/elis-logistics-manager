"""
Tenant schemas
"""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime
from typing import Literal, Optional, Union


class BankAccountDetails(BaseModel):
    bank_name: str = ''
    account_type: Optional[str] = None
    account_number: str = ''
    routing_number: str = ''

    @classmethod
    def from_stored(cls, account: dict):
        # Legacy JSON accepted null/numeric values. Normalize only the known
        # fields on an authorized read; never pass arbitrary JSON to the response.
        return cls(**{
            name: str(account[name]) if account.get(name) is not None else default
            for name, default in (
                ('bank_name', ''), ('account_type', None),
                ('account_number', ''), ('routing_number', ''),
            )
        })


class BankAccountInput(BankAccountDetails):
    model_config = ConfigDict(extra='forbid')

    @field_validator('account_number', 'routing_number')
    @classmethod
    def reject_masked_numbers(cls, value: str) -> str:
        if any(char in value for char in ('•', '*', '●')):
            raise ValueError('Provide the full number when updating a bank account.')
        return value


def mask_bank_number(value) -> str:
    if value is None or value == '':
        return ''
    number = str(value).strip()
    if not number:
        return ''
    # Never reveal an entire short/legacy value as its own "last four".
    return '••••' + (number[-4:] if len(number) > 4 else '')


class BankAccountSummary(BaseModel):
    bank_name: str = ''
    account_type: Optional[str] = None
    account_number_masked: str
    routing_number_masked: str


class BankFieldAccess(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['show', 'copy']
    account_index: int = Field(ge=0, strict=True)
    field: Literal['account_number', 'routing_number']


class BankEditAccess(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['edit']


BankDetailsAccess = Union[BankFieldAccess, BankEditAccess]


class BankFieldResponse(BaseModel):
    value: str


class BankEditResponse(BaseModel):
    bank_accounts: list[BankAccountDetails]

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
    notes: Optional[str] = None

class TenantCreate(TenantBase):
    bank_accounts: Optional[list[BankAccountInput]] = None

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
    bank_accounts: Optional[list[BankAccountInput]] = None
    notes: Optional[str] = None

class TenantResponse(TenantBase):
    bank_accounts: list[BankAccountSummary] = Field(default_factory=list)
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    @field_validator('bank_accounts', mode='before')
    @classmethod
    def summarize_bank_accounts(cls, accounts):
        # Allowlist fields; never serialize the arbitrary stored bank-account JSON.
        return [BankAccountSummary(
            bank_name=str(account.get('bank_name') or ''),
            account_type=str(account['account_type']) if account.get('account_type') is not None else None,
            account_number_masked=mask_bank_number(account.get('account_number')),
            routing_number_masked=mask_bank_number(account.get('routing_number')),
        ) for account in (accounts or [])]

    class Config:
        from_attributes = True

