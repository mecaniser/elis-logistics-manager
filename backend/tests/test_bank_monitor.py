from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from app.services.bank_monitor import MonitorRules, BalanceSnapshot, calculate, due_date, next_check, usd_cents
from app.services.truliant_reader import parse_card, BankReadError
from app.models.bank_monitor import BankMonitorConfig, BankMonitorRun
from app.models.tenant import Tenant
from app.bank_monitor_worker import run_due
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
