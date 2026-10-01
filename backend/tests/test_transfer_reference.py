from datetime import datetime, timezone
import pytest
from app.services import plaid_bank

DRAFT_ID = 'a1b2c3d4-1234-4567-89ab-0123456789ab'
MEMO = 'Cvr LifeCafe 10-01 a1b2c3d4'


def test_reference_is_bound_to_saved_draft():
    assert plaid_bank.transfer_reference(MEMO, DRAFT_ID) == 'a1b2c3d4'
    assert plaid_bank.transfer_reference('Cvr ELIS a1b2c3d4-1234', DRAFT_ID) == 'a1b2c3d4-1234'
    assert plaid_bank.transfer_reference('Cvr Other deadbeef', DRAFT_ID) is None
    assert plaid_bank.transfer_reference(MEMO, 'invalid') is None


def match(monkeypatch, debit='Principal Disbursement Cvr New label A1B2C3D4', credit='Deposit Cvr New label a1b2c3d4', extras=None):
    today = datetime.now(timezone.utc).date()
    rows = {'a': dict(transaction_id='a', account_id='credit', amount=339, pending=False, date=str(today), name=debit),
            'b': dict(transaction_id='b', account_id='checking', amount=-339, pending=False, date=str(today), name=credit)}
    rows.update(extras or {})
    monkeypatch.setattr(plaid_bank, 'synced_transactions', lambda *_: (rows, 'HISTORICAL_UPDATE_COMPLETE'))
    return plaid_bank.transfer_match('unused', {'2829': {'account_id': 'credit'}, '3304': {'account_id': 'checking'}},
        from_last4='2829', to_last4='3304', amount_cents=33900, earliest=today, memo=MEMO, draft_id=DRAFT_ID)


def test_changed_label_with_intact_id_on_both_posted_entries_matches(monkeypatch):
    result = match(monkeypatch)
    assert result['status'] == 'ready_for_confirmation'
    assert result['reference_matched'] is True


@pytest.mark.parametrize('reference', ['deadbeef', 'a1b2c3d40', 'xa1b2c3d4', 'a1b2c3d4-1234', ''])
def test_wrong_missing_or_partial_reference_never_auto_matches(monkeypatch, reference):
    result = match(monkeypatch, credit='Transfer edited label ' + reference)
    assert result['reference_matched'] is False


def test_pending_or_wrong_amount_account_date_never_matches(monkeypatch):
    # Mutate the prepared ledger fixture after it is constructed.
    for field, value in [('pending', True), ('amount', -338), ('account_id', 'other'), ('date', '2020-01-01')]:
        original = plaid_bank.synced_transactions
        match(monkeypatch)
        rows, status = plaid_bank.synced_transactions('unused', {})
        rows['b'][field] = value
        monkeypatch.setattr(plaid_bank, 'synced_transactions', lambda *_: (rows, status))
        result = plaid_bank.transfer_match('unused', {'2829': {'account_id':'credit'}, '3304': {'account_id':'checking'}}, from_last4='2829', to_last4='3304', amount_cents=33900, earliest=datetime.now(timezone.utc).date(), memo=MEMO, draft_id=DRAFT_ID)
        assert result['status'] != 'ready_for_confirmation'
        monkeypatch.setattr(plaid_bank, 'synced_transactions', original)


def test_reference_distinguishes_equal_amounts_but_duplicate_reference_stays_ambiguous(monkeypatch):
    today = str(datetime.now(timezone.utc).date())
    other = dict(transaction_id='c', account_id='credit', amount=339, pending=False, date=today, name='Transfer other deadbeef')
    assert match(monkeypatch, extras={'c':other})['reference_matched'] is True
    other['name'] = 'Transfer repeated a1b2c3d4'
    assert match(monkeypatch, extras={'c':other})['status'] == 'ambiguous'
