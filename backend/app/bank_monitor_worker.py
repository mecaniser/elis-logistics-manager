"""Run as a separate supervised process: python -m app.bank_monitor_worker.

No schedules start inside web workers. Every run is proposal-only.
"""
import os
import signal
import threading
from datetime import datetime, timedelta, timezone
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models.bank_monitor import (BankMonitorConfig, BankMonitorConnectionCheck,
                                     BankMonitorRun, BankMonitorWorkerHeartbeat, BankProviderConnection)
from app.models.tenant import Tenant
from app.services.bank_monitor import EASTERN, MonitorRules, calculate, due_date
from app.services.truliant_reader import BankReadError, read_balances
from app.services import plaid_bank


def read_provider(db, tenant_id, rules, now):
    if plaid_bank.environment() != 'production':
        raise plaid_bank.PlaidBankError('provider_not_live')
    connection = db.get(BankProviderConnection, tenant_id)
    if not connection:
        raise plaid_bank.PlaidBankError('provider_connection_required')
    try:
        token = plaid_bank.decrypt_token(connection.encrypted_access_token)
        bank_item = plaid_bank.item(token)
        if bank_item.get('item_id') != connection.item_id or bank_item.get('institution_id') != plaid_bank.TRULIANT_INSTITUTION_ID:
            raise plaid_bank.PlaidBankError('provider_institution_mismatch')
        snapshot = plaid_bank.balance_snapshot(token, rules, connection.account_map, now)
    except plaid_bank.PlaidBankError as exc:
        connection.status = 'reauthorization_required' if str(exc) == 'provider_reauthorization_required' else 'read_blocked'
        connection.last_error = str(exc)
        raise
    connection.status = 'balance_verified'
    connection.last_error = None
    connection.last_checked_at = now
    return snapshot


def provider_pending_result(snapshot, rules):
    return {'status': 'provider_pending_unverified', 'source': 'plaid',
            'observed_at': snapshot.observed_at.isoformat(),
            'accounts': [{**account.model_dump(), 'nickname': next(
                configured.nickname for configured in rules.checking if configured.last4 == account.last4)}
                         for account in snapshot.accounts if account.last4 in {a.last4 for a in rules.checking}],
            'credit_accounts': [{**account.model_dump(), 'nickname': next(
                configured.nickname for configured in rules.sources if configured.last4 == account.last4)}
                                for account in snapshot.accounts if account.last4 in {a.last4 for a in rules.sources}],
            'proposals': [], 'transfers_executed': False,
            'message': 'Current balances were read, but pending debits were not verifiable. No coverage or repayment proposal was calculated.'}


def provider_visibility(db, tenant_id):
    """Transaction feed evidence is informative, never proof of completeness."""
    connection = db.get(BankProviderConnection, tenant_id)
    if not connection:
        return {'status': 'unavailable'}
    try:
        evidence = plaid_bank.transaction_visibility(
            plaid_bank.decrypt_token(connection.encrypted_access_token), connection.account_map)
    except plaid_bank.PlaidBankError:
        return {'status': 'unavailable'}
    return {'status': 'observed', **evidence}


def run_due(db, now, reader=read_balances):
    day = due_date(now)
    if day is None:
        return 0
    mode = os.getenv('BANK_MONITOR_READER_MODE')
    chrome_reader = mode == 'signed_in_chrome'
    local = now.astimezone(EASTERN)
    allowed = {x.strip() for x in os.getenv('BANK_MONITOR_TENANT_IDS', '').split(',')}
    configs = db.query(BankMonitorConfig).filter_by(enabled=True).all()
    completed = 0
    for config in configs:
        if str(config.tenant_id) not in allowed:
            continue
        if not db.query(Tenant).filter(Tenant.id == config.tenant_id, Tenant.is_active.is_(True)).first():
            continue
        provider_linked = bool(db.get(BankProviderConnection, config.tenant_id))
        if chrome_reader and not provider_linked and (local.hour, local.minute) < (17, 45):
            continue
        if db.query(BankMonitorRun).filter_by(tenant_id=config.tenant_id, scheduled_date=day).first():
            continue
        run = BankMonitorRun(tenant_id=config.tenant_id, scheduled_date=day,
                             started_at=now, status='running', result={})
        db.add(run)
        try:
            db.commit()  # Unique daily slot prevents duplicate collectors across workers.
        except IntegrityError:
            db.rollback()
            continue
        try:
            rules = MonitorRules.model_validate(config.rules)
            use_provider = mode == 'plaid' or (chrome_reader and provider_linked)
            if chrome_reader and not use_provider:
                raise BankReadError('chrome_check_missed')
            if use_provider:
                snapshot = read_provider(db, config.tenant_id, rules, now)
                result = (provider_pending_result(snapshot, rules) if rules.basis == 'posted_and_pending'
                          else calculate(rules, snapshot, now))
                result['source'] = 'plaid_background' if chrome_reader else 'plaid'
                result['transaction_visibility'] = provider_visibility(db, config.tenant_id)
            else:
                profile = os.getenv(f'BANK_MONITOR_PROFILE_{config.tenant_id}')
                if not profile:
                    raise BankReadError('connection_required')
                snapshot = (reader(profile, rules, tenant_id=config.tenant_id)
                            if reader is read_balances else reader(profile, rules))
                result = calculate(rules, snapshot, datetime.now(timezone.utc))
            run.status = result['status']
            run.result = result
        except plaid_bank.PlaidBankError as exc:
            run.status = str(exc)
            run.result = {'transfers_executed': False,
                          'source': 'plaid_background' if chrome_reader else 'plaid'}
        except BankReadError as exc:
            run.status = str(exc)
            run.result = {'transfers_executed': False}
        except ValueError:
            run.status = 'balance_review_required'
            run.result = {'transfers_executed': False,
                          'message': 'Missing, ambiguous, or stale balance data. No proposal calculated.'}
        except Exception:
            run.status = 'check_failed'
            run.result = {'transfers_executed': False}
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        completed += 1
    return completed


def run_connection_checks(db, reader=read_balances):
    """Verify private bank access without using a daily slot or preparing a transfer."""
    mode = os.getenv('BANK_MONITOR_READER_MODE')
    # Chrome mode can check an already-consented Plaid Item in the background.
    # It must never open the old private bank browser.
    allowed = {int(value.strip()) for value in os.getenv('BANK_MONITOR_TENANT_IDS', '').split(',') if value.strip().isdigit()}
    pending = db.query(BankMonitorConnectionCheck).filter(
        BankMonitorConnectionCheck.status == 'pending',
        BankMonitorConnectionCheck.tenant_id.in_(allowed)).order_by(BankMonitorConnectionCheck.id).all()
    completed = 0
    for check in pending:
        if mode == 'signed_in_chrome' and not db.get(BankProviderConnection, check.tenant_id):
            continue
        claimed = db.query(BankMonitorConnectionCheck).filter_by(id=check.id, status='pending').update(
            {'status': 'running', 'started_at': datetime.now(timezone.utc)}, synchronize_session=False)
        db.commit()
        if not claimed:
            continue
        db.refresh(check)
        try:
            tenant = db.query(Tenant).filter(Tenant.id == check.tenant_id, Tenant.is_active.is_(True)).first()
            config = db.get(BankMonitorConfig, check.tenant_id)
            if not tenant or not config:
                raise BankReadError('connection_required')
            rules = MonitorRules.model_validate(config.rules)
            if mode == 'plaid' or (mode == 'signed_in_chrome' and db.get(BankProviderConnection, check.tenant_id)):
                snapshot = read_provider(db, check.tenant_id, rules, datetime.now(timezone.utc))
                check.status = 'balance_only' if rules.basis == 'posted_and_pending' else 'verified'
                visibility = provider_visibility(db, check.tenant_id)
            else:
                if mode == 'signed_in_chrome':
                    raise BankReadError('provider_connection_required')
                profile = os.getenv(f'BANK_MONITOR_PROFILE_{check.tenant_id}')
                if not profile:
                    raise BankReadError('connection_required')
                snapshot = (reader(profile, rules, tenant_id=check.tenant_id)
                            if reader is read_balances else reader(profile, rules))
                calculate(rules, snapshot, datetime.now(timezone.utc))
                check.status = 'verified'
            check.result = {'observed_at': snapshot.observed_at.isoformat(),
                            'account_count': len(snapshot.accounts), 'transfers_executed': False,
                            'source': 'plaid' if mode == 'plaid' or mode == 'signed_in_chrome' else 'private_worker'}
            if check.result['source'] == 'plaid':
                check.result['transaction_visibility'] = visibility
        except plaid_bank.PlaidBankError as exc:
            check.status = str(exc)
            check.result = {'transfers_executed': False}
        except BankReadError as exc:
            check.status = str(exc)
            check.result = {'transfers_executed': False}
        except ValueError:
            check.status = 'balance_review_required'
            check.result = {'transfers_executed': False}
        except Exception:
            check.status = 'check_failed'
            check.result = {'transfers_executed': False}
        check.finished_at = datetime.now(timezone.utc)
        db.commit()
        completed += 1
    return completed


def record_heartbeat(db, now):
    allowed = {int(value.strip()) for value in os.getenv('BANK_MONITOR_TENANT_IDS', '').split(',') if value.strip().isdigit()}
    # A killed browser read must never look like an endless live check or be
    # retried automatically. Login attempts have a separate durable guard.
    db.query(BankMonitorConnectionCheck).filter(
        BankMonitorConnectionCheck.tenant_id.in_(allowed),
        BankMonitorConnectionCheck.status == 'running',
        BankMonitorConnectionCheck.started_at < now - timedelta(minutes=10)).update(
            {'status': 'check_interrupted', 'finished_at': now,
             'result': {'transfers_executed': False}}, synchronize_session=False)
    for tenant_id in allowed:
        heartbeat = db.get(BankMonitorWorkerHeartbeat, tenant_id)
        if heartbeat is None:
            heartbeat = BankMonitorWorkerHeartbeat(tenant_id=tenant_id, last_seen_at=now)
            db.add(heartbeat)
        else:
            heartbeat.last_seen_at = now
    db.commit()


def main():
    if os.getenv('BANK_MONITOR_WORKER_ENABLED') != 'true':
        print('Bank monitor is disabled; no scheduled checks started.')
        return
    # Never silently start a server worker against a fallback SQLite database.
    if not os.getenv('DATABASE_URL', '').startswith(('postgres://', 'postgresql://')):
        raise SystemExit('Server worker requires an explicit PostgreSQL DATABASE_URL.')
    if not os.getenv('BANK_MONITOR_TENANT_IDS', '').strip():
        raise SystemExit('Server worker requires BANK_MONITOR_TENANT_IDS.')
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            record_heartbeat(db, now)
            run_connection_checks(db)
            run_due(db, now)
        stop.wait(30)


if __name__ == '__main__':
    main()
