import pytest
from app.services.truliant_reader import pending_total, BankReadError

PENDING = {'section': 'pending transactions section'}
POSTED = {'section': 'posted transactions section'}


def test_pending_debits_without_offsetting_pending_deposits():
    assert pending_total([PENDING, {'id': 'a', 'amount': '-$989.06'},
                          {'id': 'b', 'amount': '$1,500.00'}, POSTED]) == 98906


def test_explicit_empty_pending_section():
    assert pending_total([PENDING, POSTED]) == 0


@pytest.mark.parametrize('rows', [[], [POSTED], [PENDING],
    [PENDING, {'id': 'a', 'amount': '-$3.00'}],
    [PENDING, {'id': 'a', 'amount': 'unavailable'}, POSTED],
    [PENDING, {'id': 'a', 'amount': '-$3.00'}, {'id': 'a', 'amount': '-$3.00'}, POSTED],
    [PENDING, {'amount': '-$3.00'}, POSTED], [PENDING, PENDING, POSTED]])
def test_missing_truncated_duplicate_or_ambiguous_data_blocks(rows):
    with pytest.raises(BankReadError, match='pending_data_unavailable'):
        pending_total(rows)


def test_credit_balance_and_interest_are_not_payoff():
    from app.services.truliant_reader import credit_details
    values = credit_details([{'label': 'Balance', 'amount': '$531.25'},
                             {'label': 'Accrued Interest', 'amount': '$5.62'},
                             {'label': 'Current amount due', 'amount': '$0.00'}])
    assert values == {'outstanding_cents': 53125, 'accrued_interest_cents': 562}
    assert 'payoff_cents' not in values
    with pytest.raises(BankReadError):
        credit_details([{'label': 'Current amount due', 'amount': '$0.00'}])
    with pytest.raises(BankReadError):
        credit_details([{'label': 'Balance', 'amount': '$1.00'}, {'label': 'Balance', 'amount': '$2.00'}])
