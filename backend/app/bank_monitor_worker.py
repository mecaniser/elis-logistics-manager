"""Run as a separate supervised process: python -m app.bank_monitor_worker.

No schedules start inside web workers. Every run is proposal-only.
"""
import os
import signal
import threading
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from app.database import SessionLocal
from app.models.bank_monitor import BankMonitorConfig, BankMonitorRun
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
            snapshot = reader(profile, rules)
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
            run_due(db, datetime.now(timezone.utc))
        stop.wait(30)


if __name__ == '__main__':
    main()
