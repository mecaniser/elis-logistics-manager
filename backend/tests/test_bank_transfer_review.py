from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.auth_utils import SESSION_COOKIE_NAME, create_session_token
from app.models.bank_monitor import BankMonitorConfig, BankProviderConnection, BankRepaymentRun, BankTransferDraft
from app.services.bank_monitor import BalanceSnapshot, MonitorRules
from app.services.bank_transfer_review import build_review
from app.services import plaid_bank


def rules():
    return MonitorRules(checking=[{'nickname': 'Business', 'last4': '1111'}, {'nickname': 'Logistics', 'last4': '4444'}],
        sources=[{'nickname': 'Credit', 'last4': '2222'}, {'nickname': 'HELOC', 'last4': '3333'}],
        repayment={'enabled': False, 'priority': ['2222', '3333'], 'reserve_cents': 1000})


def snapshot(first=10000, available=8000, second=5000):
    return BalanceSnapshot(observed_at=datetime.now(timezone.utc), accounts=[
        {'last4': '1111', 'current_cents': first, 'available_cents': available},
        {'last4': '4444', 'current_cents': second, 'available_cents': second},
        {'last4': '2222', 'outstanding_cents': 9000}, {'last4': '3333', 'outstanding_cents': 100000}])


def test_review_protects_pending_once_and_allocates_each_dollar_once():
    result = build_review(rules(), snapshot(), {'status': 'observed', 'pending_debit_cents': {'1111': 2000}}, [])
    assert [a['limit_cents'] for a in result['cash_accounts']] == [7000, 4000]
    assert [(p['from_last4'], p['to_last4'], p['amount_cents']) for p in result['proposals']] == [
        ('1111', '2222', 7000), ('4444', '2222', 2000), ('4444', '3333', 2000)]
    assert result['pending_complete'] is False
    assert result['transfers_executed'] is False
    # The bank has not yet reflected a larger reported debit in available.
    result = build_review(rules(), snapshot(), {'pending_debit_cents': {'1111': 5000}}, [])
    assert result['cash_accounts'][0]['limit_cents'] == 4000


def test_unfinished_transfers_reserve_cash_and_credit_without_assuming_incoming_cash():
    drafts = [SimpleNamespace(from_last4='1111', to_last4='2222', amount_cents=5000, status='prepared_awaiting_submission')]
    result = build_review(rules(), snapshot(), {}, drafts)
    assert result['cash_accounts'][0]['limit_cents'] == 2000
    assert sum(p['amount_cents'] for p in result['proposals'] if p['to_last4'] == '2222') == 4000


def test_shortfall_blocks_repayment_and_missing_checking_blocks_all_routes():
    result = build_review(rules(), snapshot(second=-2000), {}, [])
    assert result['proposals'] == [{'kind': 'checking', 'from_last4': '1111', 'to_last4': '4444', 'amount_cents': 3000}]
    result = build_review(rules(), snapshot(available=None), {}, [])
    assert not result['proposals'] and result['issues']
    missing_debt = snapshot()
    missing_debt.accounts[2].outstanding_cents = None
    result = build_review(rules(), missing_debt, {}, [])
    assert not result['proposals'] and result['issues']


@pytest.fixture
def review_client(client, db, monkeypatch):
    monkeypatch.setenv('APP_AUTH_USERNAME', 'review-test')
    monkeypatch.setenv('APP_AUTH_SECRET', 'review-test-secret')
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    monkeypatch.setattr(plaid_bank, 'configured', lambda: True)
    monkeypatch.setattr(plaid_bank, 'environment', lambda: 'production')
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('review-test'))
    db.add(BankMonitorConfig(tenant_id=1, enabled=False, rules=rules().model_dump(), updated_at=datetime.now(timezone.utc)))
    db.add(BankProviderConnection(tenant_id=1, provider='plaid', item_id='test-item', institution_id='test',
        encrypted_access_token='not-a-token', account_map={}, status='balance_verified', linked_at=datetime.now(timezone.utc)))
    db.commit()
    from app.routers import bank_monitor
    monkeypatch.setattr(bank_monitor, 'fresh_review_read', lambda *_: (snapshot(), {'status': 'observed'}))
    return client


def headers(action):
    return {'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': action}


def create_review(client):
    response = client.post('/api/bank-monitor/transfer-reviews', json={}, headers=headers('review-bank-transfers'))
    assert response.status_code == 200, response.text
    return response.json()


def submit(client, review, amount=7000, **extra):
    return client.post(f'/api/bank-monitor/transfer-reviews/{review["id"]}/drafts',
        json={'routes': [{'from_last4': '1111', 'to_last4': '2222', 'amount_cents': amount}], **extra},
        headers=headers('create-reviewed-transfers'))


def test_prefilled_review_creates_drafts_once_without_payoff_or_manual_bank_values(review_client, db):
    review = create_review(review_client)
    assert review['result']['cash_accounts'][0]['current_cents'] == 10000
    assert submit(review_client, review, 7001).status_code == 409
    response = submit(review_client, review, 6000)
    assert response.status_code == 200, response.text
    assert response.json()['drafts'][0]['amount_cents'] == 6000
    assert response.json()['transfers_executed'] is False
    assert submit(review_client, review).status_code == 409
    assert db.query(BankTransferDraft).count() == 1


def test_review_rejects_stale_changed_settings_duplicate_routes_and_forged_evidence(review_client, db):
    review = create_review(review_client)
    assert submit(review_client, review, snapshot={}).status_code == 422
    route = {'from_last4': '1111', 'to_last4': '2222', 'amount_cents': 7000}
    response = review_client.post(f'/api/bank-monitor/transfer-reviews/{review["id"]}/drafts', json={'routes': [route, route]}, headers=headers('create-reviewed-transfers'))
    assert response.status_code == 409
    db.rollback()
    run = db.get(BankRepaymentRun, review['id'])
    old = dict(run.result)
    old['snapshot'] = {**old['snapshot'], 'observed_at': (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()}
    run.result = old
    db.commit()
    assert submit(review_client, review).status_code == 409
    fresh = create_review(review_client)
    config = db.get(BankMonitorConfig, 1)
    config.rules = {**config.rules, 'buffer_cents': 500}
    db.commit()
    assert submit(review_client, fresh).status_code == 409


def test_queue_change_invalidates_spend_and_cancel_releases_unprepared_cash(review_client, db):
    first, second = create_review(review_client), create_review(review_client)
    draft = submit(review_client, first).json()['drafts'][0]
    assert submit(review_client, second).status_code == 409
    response = review_client.post(f'/api/bank-monitor/drafts/{draft["id"]}/cancel', headers=headers('reviewed-transfer'))
    assert response.status_code == 200
    assert submit(review_client, second).status_code == 200


def test_preparation_rechecks_balances_and_never_cancels_uncertain_submission(review_client, db, monkeypatch):
    review = create_review(review_client)
    draft = submit(review_client, review).json()['drafts'][0]
    from app.routers import bank_monitor
    monkeypatch.setattr(bank_monitor, 'fresh_review_read', lambda *_: (snapshot(first=1000, available=1000), {}))
    response = review_client.post(f'/api/bank-monitor/drafts/{draft["id"]}/prepare', headers=headers('reviewed-transfer'))
    assert response.status_code == 409
    db.refresh(db.get(BankTransferDraft, draft['id']))
    assert db.get(BankTransferDraft, draft['id']).status == 'reviewed'
    db.get(BankTransferDraft, draft['id']).status = 'prepared_awaiting_submission'
    db.commit()
    assert review_client.post(f'/api/bank-monitor/drafts/{draft["id"]}/cancel', headers=headers('reviewed-transfer')).status_code == 409


def test_reference_match_requires_both_entries_and_exact_reference(monkeypatch):
    mapping = {'1111': {'account_id': 'cash'}, '2222': {'account_id': 'credit'}}
    today = datetime.now(timezone.utc).date()
    def match(debit, credit):
        rows = {'a': {'transaction_id': 'a', 'account_id': 'cash', 'amount': 70, 'pending': False, 'date': str(today), 'name': debit},
                'b': {'transaction_id': 'b', 'account_id': 'credit', 'amount': -70, 'pending': False, 'date': str(today), 'name': credit}}
        monkeypatch.setattr(plaid_bank, 'synced_transactions', lambda *_: (rows, 'HISTORICAL_UPDATE_COMPLETE'))
        return plaid_bank.transfer_match('unused', mapping, from_last4='1111', to_last4='2222', amount_cents=7000, earliest=today, memo='Rpy 2222 0925 1-1')
    assert match('Transfer Rpy 2222 0925 1-1', 'Payment Rpy 2222 0925 1-1')['reference_matched'] is True
    assert match('Transfer Rpy 2222 0925 1-1', 'Payment Rpy 2222 0925 1-10')['reference_matched'] is False
    assert match('Transfer', 'Payment')['reference_matched'] is False


def test_review_cannot_be_used_by_another_tenant_or_without_action_header(review_client, db):
    assert review_client.post('/api/bank-monitor/transfer-reviews', json={}, headers={'X-Tenant-ID': '1'}).status_code == 403
    review = create_review(review_client)
    run = db.get(BankRepaymentRun, review['id'])
    run.tenant_id = 2
    db.commit()
    assert submit(review_client, review).status_code == 409


def test_checking_coverage_draft_can_prepare_with_existing_extension_contract(review_client, monkeypatch):
    from app.routers import bank_monitor
    monkeypatch.setattr(bank_monitor, 'fresh_review_read', lambda *_: (snapshot(second=-2000), {}))
    review = create_review(review_client)
    response = review_client.post(f'/api/bank-monitor/transfer-reviews/{review["id"]}/drafts',
        json={'routes': [{'from_last4': '1111', 'to_last4': '4444', 'amount_cents': 3000}]}, headers=headers('create-reviewed-transfers'))
    assert response.status_code == 200
    draft = response.json()['drafts'][0]
    assert draft['kind'] == 'coverage' and draft['memo'].startswith('Cvr ')
    response = review_client.post(f'/api/bank-monitor/drafts/{draft["id"]}/prepare', headers=headers('reviewed-transfer'))
    assert response.status_code == 200, response.text


def test_automatic_reconciliation_requires_exact_reference_and_unique_evidence(review_client, db, monkeypatch):
    review = create_review(review_client)
    draft = submit(review_client, review).json()['drafts'][0]
    stored = db.get(BankTransferDraft, draft['id'])
    stored.status = 'prepared_awaiting_submission'
    db.commit()
    monkeypatch.setattr(plaid_bank, 'decrypt_token', lambda _: 'unused')
    monkeypatch.setattr(plaid_bank, 'item', lambda _: {'item_id': 'test-item', 'institution_id': plaid_bank.TRULIANT_INSTITUTION_ID})
    match = {'status': 'ready_for_confirmation', 'reference_matched': False,
             'source': {'transaction_id': 'debit', 'description': 'Transfer', 'date': '2026-09-25', 'amount_cents': 7000},
             'destination': {'transaction_id': 'credit', 'description': 'Payment', 'date': '2026-09-25', 'amount_cents': -7000}}
    monkeypatch.setattr(plaid_bank, 'transfer_match', lambda *_, **kwargs: match)
    path = f'/api/bank-monitor/drafts/{draft["id"]}/plaid-match'
    response = review_client.post(path, json={'automatic': True}, headers=headers('verify-plaid-transfer'))
    assert response.json()['status'] == 'ready_for_confirmation'
    db.refresh(stored)
    assert stored.status == 'prepared_awaiting_submission'
    match['reference_matched'] = True
    response = review_client.post(path, json={'automatic': True}, headers=headers('verify-plaid-transfer'))
    assert response.json()['status'] == 'bank_history_matched'
    assert response.json()['verification_source'] == 'plaid_reference_match'
