"""Prospective ownership cash flows, never evidence of payments or reserves."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

ZERO = Decimal('0')


def money(value):
    return format(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f')


@dataclass(frozen=True)
class TrailerInvestment:
    funding: Literal['cash', 'heloc', 'dealer', 'other']
    acquisition_cost: Decimal
    initial_cash: Decimal
    financed: Decimal
    annual_rate: Decimal
    months: int
    net_resale: Decimal
    monthly_allocation: Decimal
    balance_at_sale: Decimal = ZERO
    financed_fees: Decimal = ZERO
    quoted_monthly_payment: Decimal | None = None


def investment_projection(p: TrailerInvestment):
    if p.funding not in ('cash', 'heloc', 'dealer', 'other'):
        raise ValueError('Unknown funding model.')
    if not isinstance(p.months, int) or not 1 <= p.months <= 600:
        raise ValueError('Horizon must be 1–600 months.')
    values = [p.acquisition_cost, p.initial_cash, p.financed, p.annual_rate,
              p.net_resale, p.monthly_allocation, p.balance_at_sale, p.financed_fees]
    if p.quoted_monthly_payment is not None:
        values.append(p.quoted_monthly_payment)
    if any(not v.is_finite() or v < ZERO for v in values):
        raise ValueError('Inputs must be finite nonnegative amounts.')
    if p.initial_cash + p.financed != p.acquisition_cost + p.financed_fees:
        raise ValueError('Cash and borrowing must equal acquisition cost plus financed fees.')
    if p.balance_at_sale > p.financed:
        raise ValueError('Sale balance cannot exceed original borrowing.')
    if p.funding == 'cash' and (p.financed or p.annual_rate or p.quoted_monthly_payment):
        raise ValueError('Cash purchases cannot have loan payments or interest.')
    if p.funding != 'cash' and p.financed <= ZERO:
        raise ValueError('Financed plans require borrowing.')
    n = Decimal(p.months)
    rate = p.annual_rate / 12
    if not p.financed:
        calculated = ZERO
    elif not rate:
        calculated = (p.financed - p.balance_at_sale) / n
    else:
        growth = (1 + rate) ** p.months
        calculated = (p.financed * growth - p.balance_at_sale) * rate / (growth - 1)
    # Preserve the quote as a cash-flow assumption; expose its difference from
    # rate-based amortization rather than inventing an actual lender schedule.
    payment = p.quoted_monthly_payment if p.quoted_monthly_payment is not None else calculated
    payments = payment * n
    principal = p.financed - p.balance_at_sale
    financing_cost = payments - principal
    if financing_cost < ZERO:
        raise ValueError('Payments cannot repay the planned principal.')
    equity = p.net_resale - p.balance_at_sale
    # Protect only initial cash not returned through net sale equity. Principal
    # is already deducted in payments and must not be reserved a second time.
    recovery = max(p.initial_cash - equity, ZERO)
    monthly_recovery = recovery / n
    monthly_left = p.monthly_allocation - payment - monthly_recovery
    surplus = monthly_left * n
    terminal_surplus = equity + recovery - p.initial_cash
    profit = p.monthly_allocation * n - payments + equity - p.initial_cash
    return {**{key: money(value) for key, value in {
        'monthly_allocation': p.monthly_allocation, 'initial_cash': p.initial_cash,
        'financed': p.financed, 'monthly_payment': payment,
        'rate_based_monthly_payment': calculated, 'quote_payment_difference': payment - calculated,
        'monthly_cash_recovery': monthly_recovery, 'monthly_left': p.monthly_allocation - Decimal(money(payment)) - Decimal(money(monthly_recovery)),
        'total_payments': payments, 'principal_repaid': principal, 'financing_cost': financing_cost,
        'protected_cash_recovery': recovery, 'net_resale': p.net_resale,
        'balance_at_sale': p.balance_at_sale, 'sale_equity': equity,
        'operating_surplus': surplus, 'terminal_above_investment': terminal_surplus,
        'projected_profit': profit,
    }.items()}, 'cash_roi_percent': money(profit / p.initial_cash * 100) if p.initial_cash else None,
        'funding': p.funding, 'months': p.months,
        'basis': 'quoted_payment' if p.quoted_monthly_payment is not None else 'constant_rate_projection',
        'status': 'forecast_before_other_costs_and_tax'}


def plan_for_day(vehicle, day):
    plans = getattr(vehicle, 'investment_plans', None) or []
    return next((p for p in reversed(plans) if p['effective'] <= day.isoformat()), None)


def plan_end(plan):
    from datetime import date
    from calendar import monthrange
    start = date.fromisoformat(plan['start'])
    month = start.year * 12 + start.month - 1 + int(plan['months'])
    year, zero_month = divmod(month, 12)
    return date(year, zero_month + 1, min(start.day, monthrange(year, zero_month + 1)[1]))


def monthly_day_amount(monthly, day):
    """Cumulative cent rounding keeps adjacent period sums identical."""
    from calendar import monthrange
    days = Decimal(monthrange(day.year, day.month)[1])
    return Decimal(money(monthly * day.day / days)) - Decimal(money(monthly * (day.day - 1) / days))


def plan_day_targets(plan, day):
    from app.schemas.investment import InvestmentPlan
    if not plan['start'] <= day.isoformat() < plan_end(plan).isoformat():
        return ZERO, ZERO
    projection = InvestmentPlan.model_validate(plan).projection()
    return (monthly_day_amount(Decimal(projection['monthly_cash_recovery']), day),
            monthly_day_amount(Decimal(projection['monthly_payment']), day))
