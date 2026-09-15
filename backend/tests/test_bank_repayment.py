from datetime import datetime, timezone
import pytest
from app.services.bank_monitor import MonitorRules, BalanceSnapshot, calculate_repayment

NOW = datetime(2026, 9, 18, 21, 30, tzinfo=timezone.utc)


def setup():
    rules = MonitorRules(checking=[{'nickname': 'One', 'last4': '1111'}, {'nickname': 'Two', 'last4': '4444'}],
        sources=[{'nickname': 'HELOC', 'last4': '2222'}, {'nickname': 'Business', 'last4': '3333'}],
        repayment={'enabled': True, 'priority': ['3333', '2222'], 'reserve_cents': 0})
    snapshot = BalanceSnapshot(observed_at=NOW, accounts=[
        {'last4': '1111', 'current_cents': 100000, 'pending_debits_cents': 30000, 'settled_cash_cents': 70000,
         'eligible_income_cents': 100000, 'income_date': '2026-09-18'},
        {'last4': '4444', 'current_cents': 50000, 'pending_debits_cents': 10000, 'settled_cash_cents': 40000,
         'eligible_income_cents': 50000, 'income_date': '2026-09-18'},
        {'last4': '2222', 'payoff_cents': 80000}, {'last4': '3333', 'payoff_cents': 90000}])
    return rules, snapshot


def test_pending_preserved_and_business_paid_before_heloc_across_accounts():
    rules, snapshot = setup()
    result = calculate_repayment(rules, snapshot, NOW)
    assert [(p['to_last4'], p['amount_cents']) for p in result['proposals']] == [('3333', 70000), ('3333', 20000), ('2222', 20000)]
    assert result['transfers_executed'] is False


@pytest.mark.parametrize('field', ['current_cents', 'pending_debits_cents', 'settled_cash_cents', 'eligible_income_cents', 'income_date'])
def test_missing_evidence_blocks_all_repayment(field):
    rules, snapshot = setup()
    setattr(snapshot.accounts[1], field, None)
    assert calculate_repayment(rules, snapshot, NOW)['status'] == 'repayment_data_required'


def test_any_checking_shortfall_blocks_repayment():
    rules, snapshot = setup()
    snapshot.accounts[1].current_cents = 9999
    assert calculate_repayment(rules, snapshot, NOW)['status'] == 'checking_reserve_required'


def test_income_limit_and_payoff_limit():
    rules, snapshot = setup()
    snapshot.accounts[0].eligible_income_cents = 100
    snapshot.accounts[1].eligible_income_cents = 0
    snapshot.accounts[3].payoff_cents = 20
    snapshot.accounts[2].payoff_cents = 30
    assert [p['amount_cents'] for p in calculate_repayment(rules, snapshot, NOW)['proposals']] == [20, 30]


def test_friday_eastern_and_stale_data():
    rules, snapshot = setup()
    assert calculate_repayment(rules, snapshot, NOW.replace(day=19))['status'] == 'not_friday'
    assert calculate_repayment(rules, snapshot, NOW.replace(minute=36))['status'] == 'repayment_data_required'
    snapshot.accounts[0].income_date = NOW.replace(day=11).date()
    assert calculate_repayment(rules, snapshot, NOW)['status'] == 'repayment_data_required'


def test_minimum_due_is_not_payoff_and_priority_requires_configuration():
    rules, snapshot = setup()
    snapshot.accounts[3].payoff_cents = None
    assert calculate_repayment(rules, snapshot, NOW)['status'] == 'repayment_data_required'
    with pytest.raises(ValueError):
        MonitorRules.model_validate({**rules.model_dump(), 'repayment': {'enabled': True, 'priority': ['9999'], 'reserve_cents': 0}})
