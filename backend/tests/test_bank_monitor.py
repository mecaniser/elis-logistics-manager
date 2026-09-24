from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from app.services.bank_monitor import MonitorRules, BalanceSnapshot, calculate, due_date, next_check, usd_cents
from app.services.truliant_reader import parse_card, BankReadError
from app.models.bank_monitor import (BankMonitorBrowserCheck, BankMonitorConfig, BankMonitorRun,
                                     BankMonitorWorkerHeartbeat, BankMonitorConnectionCheck, BankRepaymentRun,
                                     BankTransferDraft)
from app.models.tenant import Tenant
from app.bank_monitor_worker import run_due, run_connection_checks, record_heartbeat
from app.bank_monitor_worker import main as worker_main
from app.auth_utils import create_session_token, SESSION_COOKIE_NAME


def rules(**kwargs):
    return MonitorRules(checking=[{'nickname': 'Checking', 'last4': '1111'}],
                        sources=[{'nickname': 'HELOC', 'last4': '2222'},
                                 {'nickname': 'Credit line', 'last4': '3333'}], **kwargs)


def snapshot(current=-12345, pending=None, observed=None):
    return BalanceSnapshot(observed_at=observed or datetime.now(timezone.utc), accounts=[
        {'last4': '1111', 'current_cents': current, 'available_cents': 10000, 'pending_debits_cents': pending},
        {'last4': '2222', 'available_credit_cents': 2000},
        {'last4': '3333', 'available_credit_cents': 50000},
    ])


def test_priority_split_and_actual_cash():
    result = calculate(rules(), snapshot(), datetime.now(timezone.utc))
    assert [p['amount_cents'] for p in result['proposals']] == [2000, 10345]
    assert result['status'] == 'review_required'
    assert result['transfers_executed'] is False


def test_pending_not_double_counted_and_pending_credits_not_assumed():
    result = calculate(rules(basis='posted_and_pending'), snapshot(current=1000, pending=2500), datetime.now(timezone.utc))
    assert result['accounts'][0]['needed_cents'] == 1500
    with pytest.raises(ValueError):
        calculate(rules(basis='posted_and_pending'), snapshot(), datetime.now(timezone.utc))


def test_no_shortfall_and_insufficient_credit():
    assert calculate(rules(), snapshot(current=0), datetime.now(timezone.utc))['status'] == 'no_shortfall'
    result = calculate(rules(), snapshot(current=-60000), datetime.now(timezone.utc))
    assert result['uncovered_cents'] == 8000
    assert result['status'] == 'insufficient_credit'


def test_shared_credit_not_reused():
    config = rules()
    config.checking.append(type(config.checking[0])(nickname='Second', last4='4444'))
    snap = snapshot(current=-40000)
    snap.accounts.append(type(snap.accounts[0])(last4='4444', current_cents=-40000))
    result = calculate(config, snap, datetime.now(timezone.utc))
    assert sum(p['amount_cents'] for p in result['proposals']) == 52000
    assert result['uncovered_cents'] == 28000


@pytest.mark.parametrize('seconds', [-301, 31])
def test_stale_and_future_rejected(seconds):
    now = datetime.now(timezone.utc)
    with pytest.raises(ValueError):
        calculate(rules(), snapshot(observed=now + timedelta(seconds=seconds)), now)


def test_missing_duplicate_and_fractional_inputs():
    snap = snapshot(); snap.accounts.pop()
    with pytest.raises(ValueError):
        calculate(rules(), snap, datetime.now(timezone.utc))
    with pytest.raises(ValidationError):
        MonitorRules(enabled=True)
    with pytest.raises(ValidationError):
        MonitorRules(checking=[{'nickname': 'One', 'last4': '1111'}], sources=[{'nickname': 'Two', 'last4': '1111'}])
    with pytest.raises(ValidationError):
        snapshot(current=1.5)


@pytest.mark.parametrize('date,before,after', [('2026-07-01', '21:29', '21:30'), ('2026-12-01', '22:29', '22:30')])
def test_eastern_schedule_dst(date, before, after):
    assert due_date(datetime.fromisoformat(f'{date}T{before}:00+00:00')) is None
    assert str(due_date(datetime.fromisoformat(f'{date}T{after}:00+00:00'))) == date
    assert '17:30' in next_check(datetime.fromisoformat(f'{date}T{after}:00+00:00'))


def test_card_parser():
    card = parse_card('Checking\n********1111\nAvailable Balance **\n-$1,234.56\nCurrent Balance\n-$123.45')
    assert card.current_cents == -12345
    assert card.available_cents == -123456
    assert parse_card('HELOC ********2222 Amount Due $50.00 Available Credit $2,000.01').available_credit_cents == 200001
    with pytest.raises(BankReadError):
        parse_card('Checking 1111 Balance unavailable')
    with pytest.raises(ValueError):
        usd_cents('$1,23.45')


def test_server_worker_disabled_by_default(monkeypatch):
    monkeypatch.delenv('BANK_MONITOR_WORKER_ENABLED', raising=False)
    assert worker_main() is None


def test_server_worker_rejects_local_database(monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_WORKER_ENABLED', 'true')
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    with pytest.raises(SystemExit, match='PostgreSQL'):
        worker_main()


def test_server_worker_requires_authorized_businesses(monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_WORKER_ENABLED', 'true')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://example.invalid/test')
    monkeypatch.delenv('BANK_MONITOR_TENANT_IDS', raising=False)
    with pytest.raises(SystemExit, match='BANK_MONITOR_TENANT_IDS'):
        worker_main()


@pytest.fixture
def bank_auth(monkeypatch, client):
    monkeypatch.setenv('APP_AUTH_USERNAME', 'bank-test')
    monkeypatch.setenv('APP_AUTH_SECRET', 'local-test-secret-not-a-bank-password')
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('bank-test'))
    return client


def test_auth_and_tenant_fail_closed(client, bank_auth, db):
    assert bank_auth.get('/api/bank-monitor', headers={'X-Tenant-ID': '1'}).status_code == 200
    for selector in ['2', '0', '-1', '1,2', '99999999999999999999999999999']:
        assert bank_auth.get('/api/bank-monitor', headers={'X-Tenant-ID': selector}).status_code in (400, 404)
    assert bank_auth.get('/api/bank-monitor').status_code == 400
    bank_auth.cookies.clear()
    assert bank_auth.get('/api/bank-monitor', headers={'X-Tenant-ID': '1'}).status_code == 401


def test_settings_validation_and_tenant_history(bank_auth, db):
    headers = {'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'save-settings'}
    assert bank_auth.put('/api/bank-monitor', headers=headers, json=rules(enabled=True).model_dump()).status_code == 200
    assert bank_auth.put('/api/bank-monitor', headers=headers, json={**rules().model_dump(), 'tenant_id': 2}).status_code == 422
    db.add(BankMonitorRun(tenant_id=2, scheduled_date=datetime.now().date(), started_at=datetime.now(timezone.utc), status='private', result={}))
    db.commit()
    assert bank_auth.get('/api/bank-monitor', headers=headers).json()['runs'] == []
    db.add(BankMonitorWorkerHeartbeat(tenant_id=1, last_seen_at=datetime.now(timezone.utc)))
    db.commit()
    assert bank_auth.get('/api/bank-monitor', headers=headers).json()['worker']['status'] == 'online'


def test_manual_repayment_run_is_guarded_recorded_and_tenant_scoped(bank_auth, db):
    repayment_rules = rules(enabled=True, repayment={
        'enabled': True, 'priority': ['3333', '2222'], 'reserve_cents': 0})
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=repayment_rules.model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.commit()
    today = datetime.now(timezone.utc).astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date().isoformat()
    payload = {
        'checking': [{'last4': '1111', 'current_cents': 100000,
                      'pending_debits_cents': 20000, 'settled_cash_cents': 80000,
                      'eligible_income_cents': 50000, 'income_date': today}],
        'sources': [{'last4': '3333', 'payoff_cents': 30000},
                    {'last4': '2222', 'payoff_cents': 40000}],
        'evidence_confirmed': True,
    }
    headers = {'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'run-repayment-check'}
    assert bank_auth.post('/api/bank-monitor/repayment-runs', json=payload,
                          headers={'X-Tenant-ID': '1'}).status_code == 403
    over_limit = {**payload, 'checking': [{**payload['checking'][0], 'eligible_income_cents': 80001}]}
    rejected = bank_auth.post('/api/bank-monitor/repayment-runs', json=over_limit, headers=headers)
    assert rejected.status_code == 422
    assert 'cannot exceed cash available' in rejected.json()['detail']
    assert db.query(BankRepaymentRun).count() == 0
    response = bank_auth.post('/api/bank-monitor/repayment-runs', json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()['status'] == 'review_required'
    assert [row['amount_cents'] for row in response.json()['result']['proposals']] == [30000, 20000]
    assert response.json()['result']['transfers_executed'] is False
    assert db.query(BankRepaymentRun).one().tenant_id == 1
    draft_headers = {'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'create-repayment-drafts'}
    drafts = bank_auth.post(f"/api/bank-monitor/repayment-runs/{response.json()['id']}/drafts",
                            json={}, headers=draft_headers)
    assert drafts.status_code == 200
    assert [(row['kind'], row['from_last4'], row['to_last4']) for row in drafts.json()['drafts']] == [
        ('repayment', '1111', '3333'), ('repayment', '1111', '2222')]
    assert bank_auth.post(f"/api/bank-monitor/repayment-runs/{response.json()['id']}/drafts",
                          json={}, headers=draft_headers).status_code == 409
    for draft in drafts.json()['drafts']:
        prepared = bank_auth.post(f"/api/bank-monitor/drafts/{draft['id']}/prepare", json={},
                                  headers={'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'reviewed-transfer'})
        assert prepared.status_code == 200
        db.query(BankTransferDraft).filter_by(id=draft['id']).update({'status': 'bank_history_matched'})
        db.commit()
    dashboard = bank_auth.get('/api/bank-monitor', headers={'X-Tenant-ID': '1'}).json()
    assert len(dashboard['repayment_runs']) == 1
    bad = {**payload, 'sources': [{'last4': '3333', 'payoff_cents': 30000}]}
    assert bank_auth.post('/api/bank-monitor/repayment-runs', json=bad, headers=headers).status_code == 422


def test_worker_daily_deduplication_and_failure(db, monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    monkeypatch.setenv('BANK_MONITOR_PROFILE_1', '/unused-test-profile')
    config = BankMonitorConfig(tenant_id=1, enabled=True, rules=rules(enabled=True).model_dump(), updated_at=datetime.now(timezone.utc))
    db.add(config); db.commit()
    now = datetime.now(timezone.utc).replace(hour=23)
    calls = []
    def reader(*args):
        calls.append(1)
        return snapshot()
    assert run_due(db, now, reader) == 1
    assert run_due(db, now, reader) == 0
    assert calls == [1]
    assert db.query(BankMonitorRun).one().status == 'review_required'
    def failure(*args):
        raise BankReadError('sign_in_required')
    assert run_due(db, now + timedelta(days=1), failure) == 1
    assert db.query(BankMonitorRun).order_by(BankMonitorRun.id.desc()).first().status == 'sign_in_required'


def test_browser_check_requires_complete_fresh_evidence(bank_auth, db):
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules(enabled=True).model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.commit()
    payload = {'snapshot': snapshot(current=0).model_dump(mode='json'), 'histories_verified': ['1111']}
    headers = {'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'record-browser-check'}
    assert bank_auth.post('/api/bank-monitor/browser-checks', json=payload,
                          headers={'X-Tenant-ID': '1'}).status_code == 403
    bad = {**payload, 'histories_verified': []}
    assert bank_auth.post('/api/bank-monitor/browser-checks', json=bad, headers=headers).status_code == 422
    stale = {'snapshot': snapshot(current=0, observed=datetime.now(timezone.utc) - timedelta(minutes=10)).model_dump(mode='json'),
             'histories_verified': ['1111']}
    assert bank_auth.post('/api/bank-monitor/browser-checks', json=stale, headers=headers).status_code == 422
    response = bank_auth.post('/api/bank-monitor/browser-checks', json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()['status'] == 'no_shortfall'
    assert response.json()['transfers_executed'] is False
    assert db.query(BankMonitorBrowserCheck).one().result['source'] == 'signed_in_chrome_assistant'
    dashboard = bank_auth.get('/api/bank-monitor', headers={'X-Tenant-ID': '1'}).json()
    assert dashboard['browser_check']['status'] == 'no_shortfall'


def test_chrome_mode_never_tries_server_login_and_records_missed_slot(db, monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    monkeypatch.setenv('BANK_MONITOR_READER_MODE', 'signed_in_chrome')
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules(enabled=True).model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.commit()
    def forbidden_reader(*_):
        raise AssertionError('The server browser must not log in in Chrome mode')
    assert run_due(db, datetime.fromisoformat('2026-09-24T21:44:00+00:00'), forbidden_reader) == 0
    assert run_due(db, datetime.fromisoformat('2026-09-24T21:45:00+00:00'), forbidden_reader) == 1
    assert db.query(BankMonitorRun).one().status == 'chrome_check_missed'


def test_worker_heartbeat_is_upserted(db, monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    first = datetime.now(timezone.utc)
    record_heartbeat(db, first)
    record_heartbeat(db, first + timedelta(seconds=30))
    heartbeat = db.query(BankMonitorWorkerHeartbeat).one()
    assert heartbeat.tenant_id == 1
    assert heartbeat.last_seen_at.replace(tzinfo=timezone.utc) == first + timedelta(seconds=30)


def test_worker_connection_check_verifies_real_account_evidence_without_daily_slot(db, monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    monkeypatch.setenv('BANK_MONITOR_PROFILE_1', '/private-test-profile')
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules(enabled=True).model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.add(BankMonitorConnectionCheck(tenant_id=1, requested_at=datetime.now(timezone.utc),
                                      status='pending', result={}))
    db.commit()
    assert run_connection_checks(db, lambda *_: snapshot()) == 1
    check = db.query(BankMonitorConnectionCheck).one()
    assert check.status == 'verified'
    assert check.result['account_count'] == 3
    assert check.result['transfers_executed'] is False
    assert db.query(BankMonitorRun).count() == 0


def test_chrome_mode_does_not_run_queued_private_connection_check(db, monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    monkeypatch.setenv('BANK_MONITOR_READER_MODE', 'signed_in_chrome')
    db.add(BankMonitorConnectionCheck(tenant_id=1, requested_at=datetime.now(timezone.utc),
                                      status='pending', result={}))
    db.commit()
    def forbidden_reader(*_):
        raise AssertionError('The server browser must not open in Chrome mode')
    assert run_connection_checks(db, forbidden_reader) == 0
    assert db.query(BankMonitorConnectionCheck).one().status == 'pending'


def test_worker_connection_check_records_sign_in_failure_without_retry(db, monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    monkeypatch.setenv('BANK_MONITOR_PROFILE_1', '/private-test-profile')
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules(enabled=True).model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.add(BankMonitorConnectionCheck(tenant_id=1, requested_at=datetime.now(timezone.utc),
                                      status='pending', result={}))
    db.commit()
    calls = []
    def reader(*_):
        calls.append(1)
        raise BankReadError('mfa_required')
    assert run_connection_checks(db, reader) == 1
    assert run_connection_checks(db, reader) == 0
    assert calls == [1]
    check = db.query(BankMonitorConnectionCheck).one()
    assert check.status == 'mfa_required'
    assert check.result == {'transfers_executed': False}


def test_interrupted_check_is_not_retried_or_changed_for_another_tenant(db, monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    now = datetime.now(timezone.utc)
    for tenant_id in (1, 2):
        db.add(BankMonitorConnectionCheck(tenant_id=tenant_id,
            requested_at=now - timedelta(minutes=12), started_at=now - timedelta(minutes=11),
            status='running', result={}))
    db.commit()
    record_heartbeat(db, now)
    checks = db.query(BankMonitorConnectionCheck).order_by(BankMonitorConnectionCheck.tenant_id).all()
    assert [check.status for check in checks] == ['check_interrupted', 'running']
    assert checks[0].result == {'transfers_executed': False}


def test_worker_verification_request_is_authenticated_and_rate_limited(bank_auth, db):
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules(enabled=True).model_dump(),
                             updated_at=datetime.now(timezone.utc)))
    db.add(BankMonitorWorkerHeartbeat(tenant_id=1, last_seen_at=datetime.now(timezone.utc)))
    db.commit()
    path = '/api/bank-monitor/connection-checks'
    headers = {'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'verify-worker-bank-access'}
    assert bank_auth.post(path, json={}, headers={'X-Tenant-ID': '1'}).status_code == 403
    assert bank_auth.post(path, json={'password': 'must-not-be-accepted'}, headers=headers).status_code == 422
    assert bank_auth.post(path, json={}, headers=headers).status_code == 202
    assert bank_auth.post(path, json={}, headers=headers).status_code == 409
    check = db.query(BankMonitorConnectionCheck).one()
    check.status = 'credentials_required'
    db.commit()
    assert bank_auth.post(path, json={}, headers=headers).status_code == 429
    dashboard = bank_auth.get('/api/bank-monitor', headers={'X-Tenant-ID': '1'}).json()
    assert dashboard['connection_check']['status'] == 'credentials_required'
    assert dashboard['connection_check']['result'].get('password') is None


def test_chrome_mode_rejects_new_private_connection_check(bank_auth, db, monkeypatch):
    monkeypatch.setenv('BANK_MONITOR_READER_MODE', 'signed_in_chrome')
    response = bank_auth.post('/api/bank-monitor/connection-checks', json={}, headers={
        'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'verify-worker-bank-access',
    })
    assert response.status_code == 409
    assert db.query(BankMonitorConnectionCheck).count() == 0
