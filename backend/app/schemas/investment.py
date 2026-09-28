from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from app.services.trailer_investment import TrailerInvestment, investment_projection


class InvestmentPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    funding: Literal['cash', 'heloc', 'dealer', 'other']
    lender: str = Field(default='', max_length=120)
    rate_type: Literal['fixed', 'variable'] = 'fixed'
    start: date
    effective: date
    months: int = Field(ge=1, le=600)
    acquisition_cost: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    initial_cash: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    financed: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    annual_rate: Decimal = Field(ge=0, le=1)
    net_resale: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    monthly_allocation: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    balance_at_sale: Decimal = Field(default=Decimal('0'), ge=0)
    financed_fees: Decimal = Field(default=Decimal('0'), ge=0)
    quoted_monthly_payment: Decimal | None = Field(default=None, ge=0)

    def projection(self):
        keys = TrailerInvestment.__dataclass_fields__
        return investment_projection(TrailerInvestment(**{k: getattr(self, k) for k in keys}))

    @model_validator(mode='after')
    def valid_calculation(self):
        self.projection()
        if self.effective < self.start:
            raise ValueError('Plan cannot take effect before purchase.')
        return self
