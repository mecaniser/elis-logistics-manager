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


def test_allowance_snapshot_is_production_only(db, monkeypatch):
    import json
    snapshot = {'checked_at': '2026-09-28T18:00:00Z', 'products': [{'name': 'Balance', 'used': 79, 'limit': 200, 'rate': '$0.10 / call'}]}
    monkeypatch.setenv('PLAID_ALLOWANCE_SNAPSHOT', json.dumps(snapshot))
    monkeypatch.setenv('PLAID_ENV', 'production')
    assert plaid_usage.summary(db)['allowance_snapshot'] == snapshot
    monkeypatch.setenv('PLAID_ENV', 'sandbox')
    assert plaid_usage.summary(db)['allowance_snapshot'] is None


def test_dashboard_cache_and_empty_observations(monkeypatch):
    from app.services import plaid_dashboard as service
    monkeypatch.setenv('PLAID_ENV', 'production')
    monkeypatch.setenv('PLAID_DASHBOARD_TEAM_ID', 'team')
    monkeypatch.setenv('PLAID_CLIENT_ID', 'client')
    monkeypatch.setenv('PLAID_SECRET', 'secret')
    monkeypatch.setattr(service, '_expires', 0)
    fake = Mock()
    fake.__enter__ = Mock(return_value=fake)
    fake.__exit__ = Mock(return_value=False)
    fake.post.return_value = httpx.Response(200, json={'access_token': 'private'}, request=httpx.Request('POST', 'https://production.plaid.com/oauth/token'))
    monkeypatch.setattr(service.httpx, 'Client', Mock(return_value=fake))
    rpc = Mock(return_value={'series': [{'metricName': 'balance-request', 'series': [], 'totalObservations': 0}]})
    monkeypatch.setattr(service, '_rpc', rpc)
    result = service.usage()
    assert result['metrics'][0]['observations'] == 0
    assert 'total_usd' not in result
    assert service.usage() == result
    rpc.assert_called_once()
    assert 'private' not in str(result) and 'secret' not in str(result)


def test_dashboard_failure_is_safe_and_environment_isolated(monkeypatch):
    from app.services import plaid_dashboard as service
    monkeypatch.setenv('PLAID_ENV', 'production')
    monkeypatch.setenv('PLAID_DASHBOARD_TEAM_ID', 'different-team')
    monkeypatch.setattr(service, '_expires', 0)
    monkeypatch.setattr(service.httpx, 'Client', Mock(side_effect=RuntimeError('private response')))
    assert service.usage() == {'status': 'unavailable', 'metrics': []}
    monkeypatch.setenv('PLAID_ENV', 'sandbox')
    assert service.usage() == {'status': 'not_connected', 'metrics': []}


def test_dashboard_rpc_parses_sse():
    import json
    from app.services import plaid_dashboard as service
    payload = {'jsonrpc': '2.0', 'id': 1, 'result': {'content': [{'type': 'text', 'text': '{"series":[]}'}]}}
    fake = Mock()
    fake.post.return_value = httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, text='event: message\ndata: '+json.dumps(payload)+'\n\n', request=httpx.Request('POST', 'https://api.dashboard.plaid.com/mcp/'))
    assert service._rpc(fake, 'private', 'plaid_get_usages', {}) == {'series': []}


def test_dashboard_endpoint_requires_owner(client, monkeypatch):
    from app.auth_utils import SESSION_COOKIE_NAME, create_session_token
    from app.services import plaid_dashboard
    monkeypatch.setenv('APP_AUTH_USERNAME', 'usage-owner')
    monkeypatch.setenv('APP_AUTH_SECRET', 'usage-test-secret')
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    provider = Mock(return_value={'status': 'available', 'metrics': []})
    monkeypatch.setattr(plaid_dashboard, 'usage', provider)
    client.cookies.clear()
    assert client.get('/api/bank-monitor/plaid-dashboard-usage', headers={'X-Tenant-ID': '1'}).status_code == 401
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('usage-owner'))
    assert client.get('/api/bank-monitor/plaid-dashboard-usage', headers={'X-Tenant-ID': '2'}).status_code == 404
    provider.assert_not_called()
    assert client.get('/api/bank-monitor/plaid-dashboard-usage', headers={'X-Tenant-ID': '1'}).status_code == 200
    provider.assert_called_once()
