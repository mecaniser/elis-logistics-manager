from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import httpx
import pytest
from app.models.bank_monitor import PlaidApiCall
from app.services import plaid_bank, plaid_usage


def test_summary_counts_only_current_environment_and_month(db, monkeypatch):
    monkeypatch.setenv('PLAID_ENV', 'production')
    monkeypatch.setenv('PLAID_BALANCE_RATE_USD', '0.10')
    now = datetime(2026, 9, 28, tzinfo=timezone.utc)
    for env, date, endpoint, outcome in [
        ('production', now, '/accounts/balance/get', 'successful'),
        ('production', now, '/accounts/balance/get', 'unknown'),
        ('production', now, '/transactions/sync', 'successful'),
        ('production', now, '/transactions/sync', 'failed'),
        ('sandbox', now, '/accounts/balance/get', 'successful'),
        ('production', datetime(2026, 8, 1, tzinfo=timezone.utc), '/accounts/balance/get', 'successful'),
    ]:
        db.add(PlaidApiCall(environment=env, recorded_at=date, endpoint=endpoint, outcome=outcome))
    db.commit()
    result = plaid_usage.summary(db, now)
    assert result['calls'] == 4
    assert result['successful_balance_reads'] == 1
    assert result['balance_estimate_usd'] == '0.10'
    assert result['billable_usage'] is None and result['invoice_total_usd'] is None
    monkeypatch.setenv('PLAID_BALANCE_RATE_USD', 'NaN')
    assert plaid_usage.summary(db, now)['balance_estimate_usd'] is None
    monkeypatch.setenv('PLAID_ENV', 'sandbox')
    assert plaid_usage.summary(db, now)['balance_estimate_usd'] == '0'


def test_no_records_does_not_claim_complete_zero_cost(db, monkeypatch):
    monkeypatch.setenv('PLAID_ENV', 'production')
    monkeypatch.setenv('PLAID_BALANCE_RATE_USD', '0.10')
    result = plaid_usage.summary(db)
    assert result['first_recorded_at'] is None
    assert result['balance_estimate_usd'] is None


@pytest.mark.parametrize('kind,outcome', [('success', 'successful'), ('failure', 'failed'), ('timeout', 'unknown')])
def test_provider_attempts_recorded_without_payload(monkeypatch, kind, outcome):
    monkeypatch.setattr(plaid_bank, 'configured', lambda: True)
    monkeypatch.setenv('PLAID_ENV', 'production')
    monkeypatch.setenv('PLAID_CLIENT_ID', 'private-client')
    monkeypatch.setenv('PLAID_SECRET', 'private-secret')
    recorded = Mock()
    monkeypatch.setattr(plaid_usage, 'record', recorded)
    response = SimpleNamespace(is_error=kind == 'failure', json=lambda: {'request_id': 'test'})
    monkeypatch.setattr(plaid_bank.httpx, 'post', Mock(side_effect=httpx.TimeoutException('timeout')) if kind == 'timeout' else Mock(return_value=response))
    if kind == 'success':
        plaid_bank.request('/accounts/balance/get', {'access_token': 'private-token'})
    else:
        with pytest.raises(plaid_bank.PlaidBankError):
            plaid_bank.request('/accounts/balance/get', {'access_token': 'private-token'})
    recorded.assert_called_once_with('/accounts/balance/get', 'production', outcome)


def test_usage_endpoint_is_owner_only_and_does_not_call_plaid(client, monkeypatch):
    from app.auth_utils import SESSION_COOKIE_NAME, create_session_token
    monkeypatch.setenv('APP_AUTH_USERNAME', 'usage-owner')
    monkeypatch.setenv('APP_AUTH_SECRET', 'usage-test-secret')
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    provider = Mock(side_effect=AssertionError('Usage page must not call Plaid'))
    monkeypatch.setattr(plaid_bank, 'request', provider)
    client.cookies.clear()
    assert client.get('/api/bank-monitor/plaid-usage', headers={'X-Tenant-ID': '1'}).status_code == 401
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('usage-owner'))
    assert client.get('/api/bank-monitor/plaid-usage', headers={'X-Tenant-ID': '1'}).status_code == 200
    assert client.get('/api/bank-monitor/plaid-usage', headers={'X-Tenant-ID': '2'}).status_code == 404
    provider.assert_not_called()


def test_record_failure_does_not_fail_provider_read(monkeypatch):
    monkeypatch.setenv('PLAID_USAGE_TRACKING_ENABLED', 'true')
    monkeypatch.setattr(plaid_usage, 'SessionLocal', Mock(side_effect=RuntimeError('db down')))
    plaid_usage.record('/accounts/balance/get', 'production', 'successful')
