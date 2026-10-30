from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.finance import PositiveMoney


class FinancialSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    repair_order_ids: list[str] | None = Field(default=None, max_length=1000)


class FinancialSync(FinancialSelection):
    expected_plan_digest: str = Field(pattern=r'^[0-9a-f]{64}$')


class VerifiedRepairPayment(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    expected_revision: str = Field(min_length=1, max_length=64)
    amount: PositiveMoney
    paid_date: date
    payer: Literal['business','owner','card','cash']
    transaction_id: str | None = Field(default=None, max_length=160)
    evidence_id: str | None = Field(default=None, max_length=36)
    owner_payment_confirmed: bool = False
    note: str = Field(min_length=3, max_length=2000)


class RepairPaymentReversal(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    expected_revision: str = Field(min_length=1, max_length=64)
    reversal_date: date
    reason: str = Field(min_length=3,max_length=2000)


class SourceReviewPreview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: str = Field(min_length=1,max_length=64)


class SourceReviewApply(SourceReviewPreview):
    expected_review_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    note: str = Field(min_length=3,max_length=2000)
