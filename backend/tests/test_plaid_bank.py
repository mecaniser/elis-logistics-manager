"""Contract tests for consent binding and fail-closed unattended reads."""
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from app.auth_utils import SESSION_COOKIE_NAME, create_session_token
from app.bank_monitor_worker import provider_balances_complete, read_provider, run_connection_checks, run_due
from app.models.bank_monitor import (BankMonitorConfig, BankMonitorConnectionCheck,
                                     BankMonitorRun, BankMonitorWorkerHeartbeat,
                                     BankProviderConnection)
from app.models.bank_monitor import BankTransferDraft
from app.services import plaid_bank
from app.services.bank_cash_plan import calculate_cash_plan
from app.services.bank_monitor import BalanceSnapshot, MonitorRules


def rules(basis='posted'):
    return MonitorRules(enabled=True, basis=basis,
                        checking=[{'nickname': 'Checking', 'last4': '1111'}],
                        sources=[{'nickname': 'Credit', 'last4': '2222'}])


def accounts():
    return [
        {'account_id': 'checking-id', 'mask': '1111', 'type': 'depository', 'subtype': 'checking',
         'balances': {'iso_currency_code': 'USD', 'current': -123.45, 'available': 0}},
        {'account_id': 'credit-id', 'mask': '2222', 'type': 'credit', 'subtype': 'credit card',
         'balances': {'iso_currency_code': 'USD', 'current': 200, 'available': 500}},
    ]


@pytest.fixture
def provider_env(monkeypatch):
    monkeypatch.setenv('APP_AUTH_USERNAME', 'bank-test')
    monkeypatch.setenv('APP_AUTH_SECRET', 'test-session-secret')
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    monkeypatch.setenv('BANK_MONITOR_READER_MODE', 'plaid')
    monkeypatch.setenv('PLAID_ENV', 'production')
    monkeypatch.setenv('PLAID_CLIENT_ID', 'test-client')
    monkeypatch.setenv('PLAID_SECRET', 'test-secret')
    monkeypatch.setenv('PLAID_REDIRECT_URI', 'https://example.test/bank-monitor')
    monkeypatch.setenv('BANK_MONITOR_TOKEN_KEY', Fernet.generate_key().decode())
    monkeypatch.setattr(plaid_bank, 'transaction_visibility', lambda *_: {
        'pending_entries': {'1111': 0, '2222': 0},
        'posted_entries': {'1111': 1, '2222': 0},
        'last_successful_update': '2026-09-25T17:30:00Z', 'pending_complete': False})


def test_transaction_feed_applies_posting_transition_without_claiming_completeness(monkeypatch):
    calls = iter([
        {'added': [{'transaction_id': 'pending-id', 'account_id': 'checking-id', 'pending': True}],
         'modified': [], 'removed': [], 'next_cursor': 'page-2', 'has_more': True},
        {'added': [{'transaction_id': 'posted-id', 'account_id': 'checking-id', 'pending': False}],
         'modified': [], 'removed': [{'transaction_id': 'pending-id'}],
         'next_cursor': 'done', 'has_more': False},
    ])
    def fake_request(path, _payload):
        if path == '/item/get':
            return {'status': {'transactions': {'last_successful_update': '2026-09-25T17:30:00Z'}}}
        assert path == '/transactions/sync'
        return next(calls)
    monkeypatch.setattr(plaid_bank, 'request', fake_request)
    evidence = plaid_bank.transaction_visibility('private-token', plaid_bank.map_accounts(accounts(), rules()))
    assert evidence['pending_entries'] == {'1111': 0, '2222': 0}
    assert evidence['posted_entries'] == {'1111': 1, '2222': 0}
    assert evidence['pending_complete'] is False


def test_transaction_feed_reports_observed_pending_amounts_without_double_counting(monkeypatch):
    def fake_request(path, _payload):
        if path == '/item/get':
            return {'status': {'transactions': {'last_successful_update': '2026-09-25T17:30:00Z'}}}
        return {'added': [
            {'transaction_id': 'debit', 'account_id': 'checking-id', 'pending': True,
             'amount': 125.50, 'name': 'Bill', 'authorized_date': '2026-09-25'},
            {'transaction_id': 'credit', 'account_id': 'checking-id', 'pending': True,
             'amount': -20, 'name': 'Refund', 'date': '2026-09-25'},
        ], 'modified': [], 'removed': [], 'next_cursor': 'done', 'has_more': False,
                'transactions_update_status': 'HISTORICAL_UPDATE_COMPLETE'}
    monkeypatch.setattr(plaid_bank, 'request', fake_request)
    evidence = plaid_bank.transaction_visibility('private-token', plaid_bank.map_accounts(accounts(), rules()))
    assert evidence['pending_debit_cents']['1111'] == 12550
    assert evidence['pending_debit_entries']['1111'] == 1
    assert evidence['pending_credit_cents']['1111'] == 2000
    assert evidence['pending_entries']['1111'] == 2
    assert evidence['pending_details']['1111'][0]['date'] == '2026-09-25'
    assert evidence['pending_complete'] is False


def test_cash_plan_protects_reserves_across_multiple_accounts_and_never_double_subtracts_pending():
    configured = MonitorRules(checking=[
        {'nickname': 'Operating', 'last4': '1111'}, {'nickname': 'Logistics', 'last4': '3333'}],
        sources=[{'nickname': 'Credit', 'last4': '2222'}],
        basis='posted_and_pending', buffer_cents=10000)
    snapshot = BalanceSnapshot(observed_at=datetime.now(timezone.utc), accounts=[
        {'last4': '1111', 'current_cents': 100000, 'available_cents': 80000},
        {'last4': '3333', 'current_cents': -5000, 'available_cents': -5000},
        {'last4': '2222', 'outstanding_cents': 60000, 'available_credit_cents': 5000},
    ])
    evidence = {'status': 'observed', 'pending_debit_cents': {'1111': 20000, '3333': 0},
                'pending_entries': {'1111': 1, '3333': 0}, 'pending_complete': False}
    plan = calculate_cash_plan(configured, snapshot, evidence)
    assert plan['cash_accounts'][0]['planning_limit_cents'] == 70000
    assert plan['checking_routes'] == [{'from_last4': '1111', 'to_last4': '3333', 'amount_cents': 15000}]
    assert plan['credit_routes'] == [{'from_last4': '1111', 'to_last4': '2222',
                                      'amount_cents': 55000, 'payoff_unverified': True}]
    assert plan['transfers_executed'] is False


def test_existing_consent_binds_a_newly_configured_account_when_bank_exposes_it(db, monkeypatch, provider_env):
    expanded = MonitorRules(checking=[
        {'nickname': 'Checking', 'last4': '1111'}, {'nickname': 'Second checking', 'last4': '3333'}],
        sources=[{'nickname': 'Credit', 'last4': '2222'}])
    db.add(BankProviderConnection(tenant_id=1, provider='plaid', item_id='item-id',
                                  institution_id=plaid_bank.TRULIANT_INSTITUTION_ID,
                                  encrypted_access_token=plaid_bank.encrypt_token('access-secret'),
                                  account_map=plaid_bank.map_accounts(accounts(), rules()),
                                  status='balance_verified', linked_at=datetime.now(timezone.utc)))
    db.commit()
    monkeypatch.setattr(plaid_bank, 'item', lambda _token: {
        'item_id': 'item-id', 'institution_id': plaid_bank.TRULIANT_INSTITUTION_ID})
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', lambda _token: accounts() + [
        {'account_id': 'second-checking-id', 'mask': '3333', 'type': 'depository',
         'subtype': 'checking', 'balances': {'iso_currency_code': 'USD', 'current': 20, 'available': 18}},
    ])
    snapshot = read_provider(db, 1, expanded, datetime.now(timezone.utc))
    assert {account.last4 for account in snapshot.accounts} == {'1111', '2222', '3333'}
    assert db.get(BankProviderConnection, 1).account_map['3333']['account_id'] == 'second-checking-id'


def test_plaid_transfer_match_requires_two_unique_posted_entries(monkeypatch):
    mapping = plaid_bank.map_accounts(accounts(), rules())
    monkeypatch.setattr(plaid_bank, 'synced_transactions', lambda *_: ({
        'source': {'transaction_id': 'source', 'account_id': 'checking-id',
                   'amount': 25, 'pending': False, 'date': '2026-09-25', 'name': 'Internal transfer'},
        'destination': {'transaction_id': 'destination', 'account_id': 'credit-id',
                        'amount': -25, 'pending': False, 'date': '2026-09-25', 'name': 'Payment'},
    }, 'HISTORICAL_UPDATE_COMPLETE'))
    match = plaid_bank.transfer_match('private-token', mapping, from_last4='1111',
                                      to_last4='2222', amount_cents=2500,
                                      earliest=datetime(2026, 9, 25).date())
    assert match['status'] == 'ready_for_confirmation'
    assert match['source']['transaction_id'] != match['destination']['transaction_id']
    monkeypatch.setattr(plaid_bank, 'synced_transactions', lambda *_: ({
        'source': {'transaction_id': 'source', 'account_id': 'checking-id',
                   'amount': 25, 'pending': False, 'date': '2026-09-25', 'name': 'Internal transfer'},
        'destination': {'transaction_id': 'destination', 'account_id': 'credit-id',
                        'amount': -25, 'pending': True, 'date': '2026-09-25', 'name': 'Payment'},
    }, 'HISTORICAL_UPDATE_COMPLETE'))
    assert plaid_bank.transfer_match('private-token', mapping, from_last4='1111',
        to_last4='2222', amount_cents=2500, earliest=datetime(2026, 9, 25).date())['status'] == 'posting_pending'


def test_plaid_reconciliation_requires_explicit_confirmation_and_fresh_evidence(client, db, monkeypatch, provider_env):
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('bank-test'))
    db.add(BankProviderConnection(tenant_id=1, provider='plaid', item_id='item-id',
                                  institution_id=plaid_bank.TRULIANT_INSTITUTION_ID,
                                  encrypted_access_token=plaid_bank.encrypt_token('access-secret'),
                                  account_map=plaid_bank.map_accounts(accounts(), rules()),
                                  status='balance_verified', linked_at=datetime.now(timezone.utc)))
    draft_id = str(uuid4())
    db.add(BankTransferDraft(id=draft_id, tenant_id=1, charge_reference='repayment-example',
                             amount_cents=2500, from_last4='1111', to_last4='2222',
                             memo='Rpy 2222', status='prepared_awaiting_submission',
                             created_at=datetime.now(timezone.utc)))
    db.commit()
    monkeypatch.setattr(plaid_bank, 'item', lambda _token: {
        'item_id': 'item-id', 'institution_id': plaid_bank.TRULIANT_INSTITUTION_ID})
    monkeypatch.setattr(plaid_bank, 'transfer_match', lambda *_args, **_kwargs: {
        'status': 'ready_for_confirmation',
        'source': {'transaction_id': 'source-id', 'description': 'Transfer out',
                   'date': '2026-09-25', 'amount_cents': 2500},
        'destination': {'transaction_id': 'destination-id', 'description': 'Payment in',
                        'date': '2026-09-25', 'amount_cents': -2500}})
    headers = {'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'verify-plaid-transfer'}
    probe = client.post(f'/api/bank-monitor/drafts/{draft_id}/plaid-match', json={}, headers=headers)
    assert probe.status_code == 200
    assert probe.json()['status'] == 'ready_for_confirmation'
    assert 'transaction_id' not in str(probe.json())
    assert db.get(BankTransferDraft, draft_id).status == 'prepared_awaiting_submission'
    wrong = client.post(f'/api/bank-monitor/drafts/{draft_id}/plaid-match',
                        json={'confirm': True, 'source_evidence': '0' * 64,
                              'destination_evidence': probe.json()['destination_evidence']}, headers=headers)
    assert wrong.status_code == 409
    confirmed = client.post(f'/api/bank-monitor/drafts/{draft_id}/plaid-match', json={
        'confirm': True, 'source_evidence': probe.json()['source_evidence'],
        'destination_evidence': probe.json()['destination_evidence']}, headers=headers)
    assert confirmed.status_code == 200
    assert db.get(BankTransferDraft, draft_id).status == 'bank_history_matched'


def test_connected_accounts_can_be_discovered_without_chrome_or_balance_charge(client, db, monkeypatch, provider_env):
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('bank-test'))
    db.add(BankProviderConnection(tenant_id=1, provider='plaid', item_id='item-id',
                                  institution_id=plaid_bank.TRULIANT_INSTITUTION_ID,
                                  encrypted_access_token=plaid_bank.encrypt_token('access-secret'),
                                  account_map=plaid_bank.map_accounts(accounts(), rules()),
                                  status='balance_verified', linked_at=datetime.now(timezone.utc)))
    db.commit()
    monkeypatch.setattr(plaid_bank, 'item', lambda _token: {
        'item_id': 'item-id', 'institution_id': plaid_bank.TRULIANT_INSTITUTION_ID})
    def fake_request(path, _payload):
        assert path == '/accounts/get'
        return {'accounts': accounts() + [
            {'account_id': 'new-id', 'mask': '3333', 'type': 'depository',
             'subtype': 'checking', 'name': 'Second checking'}]}
    monkeypatch.setattr(plaid_bank, 'request', fake_request)
    result = client.get('/api/bank-monitor/provider/accounts', headers={
        'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'discover-provider-accounts'})
    assert result.status_code == 200
    assert {'nickname': 'Second checking', 'last4': '3333', 'kind': 'checking'} in result.json()['accounts']
    assert 'account_id' not in str(result.json())


def test_account_binding_and_incomplete_balances(monkeypatch, provider_env):
    mapping = plaid_bank.map_accounts(accounts(), rules())
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', lambda _: accounts())
    snap = plaid_bank.balance_snapshot('private-token', rules(), mapping)
    assert snap.accounts[0].current_cents == -12345
    assert snap.accounts[1].available_credit_cents == 50000
    assert snap.accounts[0].pending_debits_cents is None
    with pytest.raises(plaid_bank.PlaidBankError, match='provider_account_mapping_required'):
        plaid_bank.map_accounts(accounts() + [accounts()[0]], rules())
    bad = accounts(); bad[1]['balances']['available'] = None
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', lambda _: bad)
    partial = plaid_bank.balance_snapshot('private-token', rules(), mapping)
    assert partial.accounts[1].available_credit_cents is None
    assert not provider_balances_complete(partial, rules())


def test_link_requests_credit_and_transaction_access(monkeypatch, provider_env):
    requested = {}
    def fake_request(path, body):
        requested.update(body)
        assert path == '/link/token/create'
        return {'link_token': 'link-token'}
    monkeypatch.setattr(plaid_bank, 'request', fake_request)
    assert plaid_bank.link_token(1) == 'link-token'
    assert requested['products'] == ['transactions', 'liabilities']
    assert requested['redirect_uri'] == 'https://example.test/bank-monitor'


def test_consent_is_tenant_bound_one_use_and_token_is_encrypted(client, db, monkeypatch, provider_env):
    # Consent can be staged while the existing Chrome reader still runs.
    monkeypatch.setenv('BANK_MONITOR_READER_MODE', 'signed_in_chrome')
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('bank-test'))
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules().model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.commit()
    monkeypatch.setattr(plaid_bank, 'link_token', lambda *_args, **_kwargs: 'link-token')
    monkeypatch.setattr(plaid_bank, 'exchange', lambda _token: ('access-secret', 'item-id'))
    monkeypatch.setattr(plaid_bank, 'item', lambda _token: {
        'item_id': 'item-id', 'institution_id': plaid_bank.TRULIANT_INSTITUTION_ID})
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', lambda _token: accounts())
    start = client.post('/api/bank-monitor/provider/link-token', json={}, headers={
        'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'start-provider-link'})
    assert start.status_code == 200
    payload = {**start.json(), 'public_token': 'public-one-use'}
    assert client.post('/api/bank-monitor/provider/exchange', json=payload, headers={
        'X-Tenant-ID': '1'}).status_code == 403
    finish_headers = {'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'finish-provider-link'}
    assert client.post('/api/bank-monitor/provider/exchange', json={**payload, 'link_token': 'wrong'},
                       headers=finish_headers).status_code == 409
    result = client.post('/api/bank-monitor/provider/exchange', json=payload, headers=finish_headers)
    assert result.status_code == 200
    assert client.post('/api/bank-monitor/provider/exchange', json=payload, headers=finish_headers).status_code == 409
    connection = db.get(BankProviderConnection, 1)
    assert 'access-secret' not in connection.encrypted_access_token
    assert plaid_bank.decrypt_token(connection.encrypted_access_token) == 'access-secret'
    dashboard = client.get('/api/bank-monitor', headers={'X-Tenant-ID': '1'}).json()
    assert dashboard['provider_connection']['linked'] is True
    assert 'access-secret' not in str(dashboard)
    assert 'item-id' not in str(dashboard)


def test_unattended_pending_rule_never_prepares_proposal(db, monkeypatch, provider_env):
    config = BankMonitorConfig(tenant_id=1, enabled=True, rules=rules('posted_and_pending').model_dump(),
                               updated_at=datetime.now(timezone.utc))
    db.add(config)
    db.add(BankProviderConnection(tenant_id=1, provider='plaid', item_id='item-id',
                                  institution_id=plaid_bank.TRULIANT_INSTITUTION_ID,
                                  encrypted_access_token=plaid_bank.encrypt_token('access-secret'),
                                  account_map=plaid_bank.map_accounts(accounts(), rules()),
                                  status='linked_unverified', linked_at=datetime.now(timezone.utc)))
    db.add(BankMonitorConnectionCheck(tenant_id=1, requested_at=datetime.now(timezone.utc),
                                      status='pending', result={}))
    db.commit()
    monkeypatch.setattr(plaid_bank, 'item', lambda _token: {
        'item_id': 'item-id', 'institution_id': plaid_bank.TRULIANT_INSTITUTION_ID})
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', lambda _token: accounts())
    def forbidden_browser(*_args, **_kwargs):
        raise AssertionError('Provider mode must not open the bank browser')
    assert run_connection_checks(db, forbidden_browser) == 1
    assert db.query(BankMonitorConnectionCheck).one().status == 'balance_only'
    assert run_due(db, datetime.fromisoformat('2026-09-24T22:00:00+00:00'), forbidden_browser) == 1
    run = db.query(BankMonitorRun).one()
    assert run.status == 'provider_pending_unverified'
    assert run.result['proposals'] == []
    assert run.result['transfers_executed'] is False


def test_chrome_mode_gets_unattended_plaid_observation_without_preparing_transfer(db, monkeypatch, provider_env):
    monkeypatch.setenv('BANK_MONITOR_READER_MODE', 'signed_in_chrome')
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules('posted_and_pending').model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.add(BankProviderConnection(tenant_id=1, provider='plaid', item_id='item-id',
                                  institution_id=plaid_bank.TRULIANT_INSTITUTION_ID,
                                  encrypted_access_token=plaid_bank.encrypt_token('access-secret'),
                                  account_map=plaid_bank.map_accounts(accounts(), rules()),
                                  status='linked_unverified', linked_at=datetime.now(timezone.utc)))
    db.add(BankMonitorConnectionCheck(tenant_id=1, requested_at=datetime.now(timezone.utc),
                                      status='pending', result={}))
    db.commit()
    monkeypatch.setattr(plaid_bank, 'item', lambda _token: {
        'item_id': 'item-id', 'institution_id': plaid_bank.TRULIANT_INSTITUTION_ID})
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', lambda _token: accounts())
    def forbidden_browser(*_args, **_kwargs):
        raise AssertionError('Chrome mode must not open a server browser')
    assert run_connection_checks(db, forbidden_browser) == 1
    check = db.query(BankMonitorConnectionCheck).one()
    assert check.status == 'balance_only'
    assert check.result['transaction_visibility']['pending_complete'] is False
    assert {row['last4'] for row in check.result['accounts']} == {'1111', '2222'}
    assert run_due(db, datetime.fromisoformat('2026-09-25T21:30:00+00:00'), forbidden_browser) == 1
    run = db.query(BankMonitorRun).one()
    assert run.status == 'provider_pending_unverified'
    assert run.result['source'] == 'plaid_background'
    assert run.result['proposals'] == []


def test_chrome_mode_allows_explicit_plaid_check_when_linked(client, db, monkeypatch, provider_env):
    monkeypatch.setenv('BANK_MONITOR_READER_MODE', 'signed_in_chrome')
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('bank-test'))
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules('posted_and_pending').model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.add(BankProviderConnection(tenant_id=1, provider='plaid', item_id='item-id',
                                  institution_id=plaid_bank.TRULIANT_INSTITUTION_ID,
                                  encrypted_access_token=plaid_bank.encrypt_token('access-secret'),
                                  account_map=plaid_bank.map_accounts(accounts(), rules()),
                                  status='balance_verified', linked_at=datetime.now(timezone.utc)))
    db.add(BankMonitorWorkerHeartbeat(tenant_id=1, last_seen_at=datetime.now(timezone.utc)))
    db.commit()
    response = client.post('/api/bank-monitor/connection-checks', json={}, headers={
        'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'verify-worker-bank-access'})
    assert response.status_code == 202
    assert db.query(BankMonitorConnectionCheck).one().status == 'pending'


def test_foreign_institution_cannot_be_saved(client, db, monkeypatch, provider_env):
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('bank-test'))
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules().model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.commit()
    monkeypatch.setattr(plaid_bank, 'link_token', lambda *_args, **_kwargs: 'link-token')
    monkeypatch.setattr(plaid_bank, 'exchange', lambda _token: ('access-secret', 'item-id'))
    monkeypatch.setattr(plaid_bank, 'item', lambda _token: {'item_id': 'item-id', 'institution_id': 'other-bank'})
    started = client.post('/api/bank-monitor/provider/link-token', json={}, headers={
        'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'start-provider-link'})
    assert started.status_code == 200
    result = client.post('/api/bank-monitor/provider/exchange', json={**started.json(), 'public_token': 'public'},
                         headers={'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'finish-provider-link'})
    assert result.status_code == 422
    assert result.json()['detail'] == 'provider_institution_mismatch'
    assert db.get(BankProviderConnection, 1) is None


def test_expired_provider_access_requires_reauthorization(db, monkeypatch, provider_env):
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules().model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.add(BankProviderConnection(tenant_id=1, provider='plaid', item_id='item-id',
                                  institution_id=plaid_bank.TRULIANT_INSTITUTION_ID,
                                  encrypted_access_token=plaid_bank.encrypt_token('access-secret'),
                                  account_map=plaid_bank.map_accounts(accounts(), rules()),
                                  status='balance_verified', linked_at=datetime.now(timezone.utc)))
    db.add(BankMonitorConnectionCheck(tenant_id=1, requested_at=datetime.now(timezone.utc),
                                      status='pending', result={}))
    db.commit()
    def expired(_token):
        raise plaid_bank.PlaidBankError('provider_reauthorization_required')
    monkeypatch.setattr(plaid_bank, 'item', expired)
    assert run_connection_checks(db) == 1
    assert db.query(BankMonitorConnectionCheck).one().status == 'provider_reauthorization_required'
    provider = db.get(BankProviderConnection, 1)
    assert provider.status == 'reauthorization_required'
    assert provider.last_error == 'provider_reauthorization_required'
