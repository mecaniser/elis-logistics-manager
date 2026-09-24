"""Strict money and command contracts; no client tenant or float money fields."""
from datetime import date
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from decimal import Decimal

Money = Annotated[str, StringConstraints(pattern=r'^-?[0-9]{1,16}\.[0-9]{2}$', max_length=20)]
PositiveMoney = Annotated[str, StringConstraints(pattern=r'^[0-9]{1,16}\.[0-9]{2}$', max_length=20)]
Quantity = Annotated[str, StringConstraints(pattern=r'^[0-9]+(?:\.[0-9]{1,4})?$', max_length=20)]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Policy(Strict):
    kind: Literal['policy']
    timezone: str
    books_basis: Literal['accrual'] = 'accrual'
    tax_classification: Literal['schedule_c'] = 'schedule_c'
    approved: bool = False
    opening_confirmed: bool = False
    account_coverage_confirmed: bool = False
    history_confirmed: bool = False
    carrier_presentation_confirmed: bool = False
    owner_treatment_confirmed: bool = False
    depreciation_confirmed: bool = False
    tax_basis_confirmed: bool = False
    repair_weekly_target: PositiveMoney = '300.00'
    evidence_ids: list[str] = Field(default_factory=list)


class RetentionTargets(Strict):
    kind: Literal['retention_targets']
    target_percent: PositiveMoney = '30.00'
    acceptable_percent: PositiveMoney = '28.00'

    @model_validator(mode='after')
    def validate_thresholds(self):
        if not 0 < Decimal(self.acceptable_percent) <= Decimal(self.target_percent) <= 100:
            raise ValueError('Use 0 < acceptable retention <= target retention <= 100 percent.')
        return self


class Account(Strict):
    kind: Literal['account']
    name: str = Field(min_length=1, max_length=100)
    account_type: Literal['bank', 'card']


class CSVMapping(Strict):
    kind: Literal['csv_mapping']
    name: str = Field(min_length=1, max_length=100)
    date_column: str
    amount_column: str
    description_column: str
    id_column: str
    date_format: Literal['%Y-%m-%d', '%m/%d/%Y'] = '%Y-%m-%d'
    invert_sign: bool = False
    approved_for_matching: bool = False


class Statement(Strict):
    kind: Literal['statement']
    account_id: str
    evidence_id: str
    mapping_id: str
    start: date
    end: date
    opening: Money
    closing: Money
    supersedes_id: str | None = None


class Claim(Strict):
    kind: Literal['bill', 'owner_advance']
    legacy_repair_id: int | None = Field(default=None, gt=0)
    evidence_id: str
    source_ref: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=500)
    amount: PositiveMoney
    asset_id: int | None = None
    pair_id: int | None = None
    category: Literal['repairs', 'fuel', 'insurance', 'tolls', 'driver_pay', 'support', 'overhead', 'interest', 'equipment']
    reserve_id: str | None = None


class Payment(Strict):
    kind: Literal['payment']
    claim_id: str
    amount: PositiveMoney
    payer: Literal['business', 'owner', 'card']
    transaction_id: str | None = None
    evidence_id: str | None = None
    principal: PositiveMoney = '0.00'
    interest: PositiveMoney = '0.00'


class CreditNote(Strict):
    kind: Literal['credit_note']
    claim_id: str
    amount: PositiveMoney
    evidence_id: str
    description: str = Field(min_length=1, max_length=500)
    transaction_id: str | None = None


class BankMatch(Strict):
    kind: Literal['bank_match']
    transaction_id: str
    target_id: str | None = None
    match_type: Literal['settlement', 'asset_sale', 'owner_contribution', 'owner_distribution', 'card_repayment', 'transfer']
    counterpart_transaction_id: str | None = None
    operating_amount: PositiveMoney = '0.00'
    investing_amount: PositiveMoney = '0.00'
    financing_amount: PositiveMoney = '0.00'


class Reserve(Strict):
    kind: Literal['reserve']
    pair_id: int
    asset_id: int | None = None
    purpose: Literal['repair', 'capital']
    amount: Money
    evidence_id: str
    opening: bool = False
    note: str = Field(min_length=1, max_length=500)


class Assignment(Strict):
    kind: Literal['assignment']
    truck_id: int
    trailer_id: int
    end: date | None = None


class AssetPlan(Strict):
    kind: Literal['asset_plan']
    asset_id: int
    acquired: date
    acquisition_cost: PositiveMoney
    expected_resale: PositiveMoney
    selling_costs: PositiveMoney = '0.00'
    planned_sale: date
    evidence_id: str
    payoff_confirmed: bool = False
    payoff_evidence_id: str | None = None


class Disposal(Strict):
    kind: Literal['disposal']
    asset_id: int
    gross_sale: PositiveMoney
    selling_costs: PositiveMoney
    book_accumulated_depreciation: PositiveMoney
    financing_payoff: PositiveMoney = '0.00'
    evidence_id: str


class Financing(Strict):
    kind: Literal['financing']
    action: Literal['draw', 'rate', 'interest', 'principal_payment', 'commitment']
    facility: str = Field(min_length=1, max_length=100)
    amount: PositiveMoney = '0.00'
    business_amount: PositiveMoney = '0.00'
    annual_rate: Quantity = '6.5'
    asset_id: int | None = None
    owner_claim_id: str | None = None
    payment_id: str | None = None
    due: date | None = None
    evidence_id: str
    use_description: str = Field(min_length=1, max_length=500)


class FuelRow(Strict):
    date: date
    gallons: Quantity | None = None
    amount: Money
    product: Literal['diesel', 'def', 'unknown'] = 'unknown'
    location: str = ''
    discount: Money | None = None
    source_row: str
    page: int | None = None


class LoadRow(Strict):
    load_id: str
    pickup: date
    delivery: date
    empty_miles: Quantity
    loaded_miles: Quantity
    freight_gross: Money
    source_row: str


class SettlementInput(Strict):
    kind: Literal['settlement']
    evidence_id: str
    source_ref: str
    asset_id: int
    trailer_id: int | None = None
    period_start: date
    period_end: date
    freight_gross: PositiveMoney
    carrier_retention: Money
    deductions: dict[str, Money]
    reported_payout: Money
    cash_adjustments: Money = '0.00'
    miles: Quantity | None = None
    mileage_basis: Literal['reported', 'independent', 'estimated', 'allocated'] = 'reported'
    fuel: list[FuelRow] = Field(default_factory=list)
    loads: list[LoadRow] = Field(default_factory=list)
    legacy_id: int | None = None


class Travel(Strict):
    kind: Literal['travel']
    asset_id: int
    start: date
    end: date
    miles: Quantity
    basis: Literal['motive', 'odometer', 'estimated']
    consumed_gallons: Quantity | None = None
    consumption_supported: bool = False
    evidence_id: str
    classification: Literal['loaded', 'deadhead', 'maintenance', 'repositioning', 'unresolved'] = 'unresolved'
    baseline_mpg: Quantity | None = None


class CompletedLoad(Strict):
    kind: Literal['completed_load']
    asset_id: int
    load_id: str
    evidence_id: str
    settlement_cycle_days: int = Field(default=7, ge=1, le=90)


class JournalLine(Strict):
    account: str
    debit: PositiveMoney = '0.00'
    credit: PositiveMoney = '0.00'
    asset_id: int | None = None


class Journal(Strict):
    kind: Literal['journal']
    cash_flow_classification: Literal['operating', 'investing', 'financing', 'opening', 'noncash'] = 'noncash'
    description: str = Field(min_length=1, max_length=500)
    evidence_id: str
    lines: list[JournalLine] = Field(min_length=2, max_length=200)


class Reversal(Strict):
    kind: Literal['reversal']
    posting_id: str
    reason: str = Field(min_length=1, max_length=500)


class Activation(Strict):
    kind: Literal['activate_finance']
    report_id: str
    browser_acceptance_confirmed: bool


class Period(Strict):
    kind: Literal['close_period', 'reopen_period']
    start: date
    end: date
    reason: str = Field(min_length=1, max_length=500)


Payload = Annotated[Union[Policy, RetentionTargets, Account, CSVMapping, Statement, Claim, Payment, CreditNote, BankMatch, Reserve, Assignment, AssetPlan, Disposal, Financing, SettlementInput, Travel, CompletedLoad, Journal, Reversal, Period, Activation], Field(discriminator='kind')]


class Command(Strict):
    effective_date: date
    payload: Payload


class ReportRequest(Strict):
    start: date
    end: date
    as_of: date

    @model_validator(mode='after')
    def ordered(self):
        if self.end < self.start or self.end > self.as_of:
            raise ValueError('Period end must be between start and as-of date.')
        return self


class MotiveRequest(Strict):
    asset_id: int
    vehicle_id: int = Field(gt=0)
    start: date
    end: date
    updated_after: str = '1970-01-01T00:00:00Z'


class ReconstructionRequest(Strict):
    legacy_ids: list[int] = Field(min_length=1, max_length=20)
