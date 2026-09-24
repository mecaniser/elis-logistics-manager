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
                                     BankMonitorRun, BankMonitorWorkerHeartbeat)
from app.models.tenant import Tenant
from app.services.bank_monitor import MonitorRules, calculate, due_date
from app.services.truliant_reader import BankReadError, read_balances


def run_due(db, now, reader=read_balances):
    day = due_date(now)
    if day is None:
        return 0
    allowed = {x.strip() for x in os.getenv('BANK_MONITOR_TENANT_IDS', '').split(',')}
    configs = db.query(BankMonitorConfig).filter_by(enabled=True).all()
    completed = 0
    for config in configs:
        if str(config.tenant_id) not in allowed:
            continue
        if not db.query(Tenant).filter(Tenant.id == config.tenant_id, Tenant.is_active.is_(True)).first():
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
            profile = os.getenv(f'BANK_MONITOR_PROFILE_{config.tenant_id}')
            if not profile:
                raise BankReadError('connection_required')
            snapshot = (reader(profile, rules, tenant_id=config.tenant_id)
                        if reader is read_balances else reader(profile, rules))
            result = calculate(rules, snapshot, datetime.now(timezone.utc))
            run.status = result['status']
            run.result = result
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
    allowed = {int(value.strip()) for value in os.getenv('BANK_MONITOR_TENANT_IDS', '').split(',') if value.strip().isdigit()}
    pending = db.query(BankMonitorConnectionCheck).filter(
        BankMonitorConnectionCheck.status == 'pending',
        BankMonitorConnectionCheck.tenant_id.in_(allowed)).order_by(BankMonitorConnectionCheck.id).all()
    completed = 0
    for check in pending:
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
            profile = os.getenv(f'BANK_MONITOR_PROFILE_{check.tenant_id}')
            if not profile:
                raise BankReadError('connection_required')
            snapshot = (reader(profile, rules, tenant_id=check.tenant_id)
                        if reader is read_balances else reader(profile, rules))
            calculate(rules, snapshot, datetime.now(timezone.utc))
            check.status = 'verified'
            check.result = {'observed_at': snapshot.observed_at.isoformat(),
                            'account_count': len(snapshot.accounts), 'transfers_executed': False}
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
