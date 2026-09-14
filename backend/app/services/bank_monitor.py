"""Balance monitoring and proposal calculation. This module cannot move money."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

EASTERN = ZoneInfo('America/New_York')


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AccountRule(StrictModel):
    nickname: str = Field(min_length=1, max_length=80)
    last4: str = Field(pattern=r'^\d{4}$')


class RepaymentRules(StrictModel):
    enabled: bool = False
    priority: List[str] = Field(default_factory=list, max_length=5)
    reserve_cents: Optional[int] = Field(default=None, ge=0, le=100000000, strict=True)


class MonitorRules(StrictModel):
    repayment: RepaymentRules = Field(default_factory=RepaymentRules)
    enabled: bool = False
    checking: List[AccountRule] = Field(default_factory=list, max_length=10)
    # Ordered by the user; never infer funding authority from account ownership.
    sources: List[AccountRule] = Field(default_factory=list, max_length=5)
    basis: Literal['posted', 'posted_and_pending'] = 'posted'
    buffer_cents: int = Field(default=0, ge=0, le=100000000, strict=True)

    @model_validator(mode='after')
    def unique_accounts(self):
        keys = [a.last4 for a in self.checking + self.sources]
        if len(keys) != len(set(keys)):
            raise ValueError('Account suffixes must be unique across checking and funding sources.')
        if self.enabled and (not self.checking or not self.sources):
            raise ValueError('Choose checking accounts and funding sources before enabling checks.')
        priority = self.repayment.priority
        if len(priority) != len(set(priority)) or any(x not in {a.last4 for a in self.sources} for x in priority):
            raise ValueError('Repayment priorities must be unique configured credit sources.')
        if self.repayment.enabled and (not self.checking or not priority or self.repayment.reserve_cents is None):
            raise ValueError('Repayment needs checking accounts, credit priority and an explicit reserve.')
        return self


class AccountBalance(StrictModel):
    last4: str = Field(pattern=r'^\d{4}$')
    current_cents: Optional[int] = Field(default=None, strict=True)
    available_cents: Optional[int] = Field(default=None, strict=True)
    available_credit_cents: Optional[int] = Field(default=None, ge=0, strict=True)
    # Verified cash withdrawable without borrowing, after holds. Never use the
    # bank's generic available balance as a substitute for this value.
    settled_cash_cents: Optional[int] = Field(default=None, strict=True)
    eligible_income_cents: Optional[int] = Field(default=None, ge=0, strict=True)
    income_date: Optional[date] = None
    # Full amount owed, not amount due or available credit.
    payoff_cents: Optional[int] = Field(default=None, ge=0, strict=True)
    pending_debits_cents: Optional[int] = Field(default=None, ge=0, strict=True)


class BalanceSnapshot(StrictModel):
    observed_at: datetime
    accounts: List[AccountBalance]

    @model_validator(mode='after')
    def valid_snapshot(self):
        if self.observed_at.tzinfo is None:
            raise ValueError('Snapshot time must include a timezone.')
        keys = [a.last4 for a in self.accounts]
        if len(keys) != len(set(keys)):
            raise ValueError('Ambiguous account suffixes.')
        return self


def due_date(now: datetime):
    """One daily slot at 17:30 Eastern, DST-aware, with same-day catch-up."""
    local = now.astimezone(EASTERN)
    return local.date() if (local.hour, local.minute) >= (17, 30) else None


def next_check(now: datetime):
    local = now.astimezone(EASTERN)
    target = local.replace(hour=17, minute=30, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target.isoformat()


def calculate(rules: MonitorRules, snapshot: BalanceSnapshot, now: datetime):
    age = (now - snapshot.observed_at).total_seconds()
    if age < -30 or age > 300:
        raise ValueError('Balance snapshot is stale or has an invalid timestamp.')
    balances = {a.last4: a for a in snapshot.accounts}
    for account in rules.checking + rules.sources:
        if account.last4 not in balances:
            raise ValueError('A configured account is missing from the bank response.')
    capacity = {}
    for source in rules.sources:
        credit = balances[source.last4].available_credit_cents
        if credit is None:
            raise ValueError('Funding source available credit is missing.')
        capacity[source.last4] = credit
    proposals, accounts = [], []
    total_gap = 0
    for account in rules.checking:
        balance = balances[account.last4]
        if balance.current_cents is None:
            raise ValueError('Checking current balance is missing.')
        pending = 0
        if rules.basis == 'posted_and_pending':
            if balance.pending_debits_cents is None:
                raise ValueError('Pending debits could not be verified. No proposal calculated.')
            pending = balance.pending_debits_cents
        # Current balance excludes pending transactions. Never subtract pending
        # from available balance, which can already include holds/credit coverage.
        need = max(0, rules.buffer_cents - balance.current_cents + pending)
        remaining = need
        for source in rules.sources:
            amount = min(remaining, capacity[source.last4])
            if amount:
                proposals.append({'from_last4': source.last4, 'to_last4': account.last4,
                                  'amount_cents': amount})
                capacity[source.last4] -= amount
                remaining -= amount
        total_gap += remaining
        accounts.append({**balance.model_dump(), 'nickname': account.nickname,
                         'needed_cents': need, 'uncovered_cents': remaining})
    return {'status': 'insufficient_credit' if total_gap else ('review_required' if proposals else 'no_shortfall'),
            'accounts': accounts, 'proposals': proposals, 'uncovered_cents': total_gap,
            'observed_at': snapshot.observed_at.isoformat(), 'basis': rules.basis,
            'repayment': calculate_repayment(rules, snapshot, now),
            'transfers_executed': False}


def usd_cents(text: str):
    import re
    value = text.strip().replace('−', '-')
    if not re.fullmatch(r'-?\$(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}', value):
        raise ValueError('Unrecognized bank amount.')
    return int(Decimal(value.replace('$', '').replace(',', '')) * 100)


def calculate_repayment(rules: MonitorRules, snapshot: BalanceSnapshot, now: datetime):
    """Friday income sweep proposals; missing evidence always blocks repayment."""
    def result(status, proposals=None):
        return {'status': status, 'proposals': proposals or [], 'transfers_executed': False}
    policy = rules.repayment
    if not policy.enabled:
        return result('disabled')
    today = now.astimezone(EASTERN).date()
    if today.weekday() != 4:
        return result('not_friday')
    if not -30 <= (now - snapshot.observed_at).total_seconds() <= 300:
        return result('repayment_data_required')
    balances = {a.last4: a for a in snapshot.accounts}
    cash = {}
    for checking in rules.checking:
        account = balances.get(checking.last4)
        if account is None or any(value is None for value in (
                account.current_cents, account.pending_debits_cents,
                account.settled_cash_cents, account.eligible_income_cents,
                policy.reserve_cents)) or account.income_date != today:
            return result('repayment_data_required')
        # Protect ALL monitored checking accounts before proposing any repayment.
        # Use min, not subtraction from available, to avoid counting holds twice.
        free = min(account.current_cents - account.pending_debits_cents,
                   account.settled_cash_cents)
        reserve = max(policy.reserve_cents, rules.buffer_cents)
        if free < reserve:
            return result('checking_reserve_required')
        cash[checking.last4] = min(free - reserve, account.eligible_income_cents)
    debt = {}
    for suffix in policy.priority:
        account = balances.get(suffix)
        if account is None or account.payoff_cents is None:
            return result('repayment_data_required')
        debt[suffix] = account.payoff_cents
    proposals = []
    for checking in rules.checking:
        for suffix in policy.priority:
            amount = min(cash[checking.last4], debt[suffix])
            if amount:
                proposals.append({'from_last4': checking.last4, 'to_last4': suffix,
                                  'amount_cents': amount})
                cash[checking.last4] -= amount
                debt[suffix] -= amount
    return result('review_required' if proposals else 'no_repayment_needed', proposals)
