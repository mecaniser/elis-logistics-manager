"""Credential-free telemetry for this ELIS integration, not a Plaid invoice."""
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from sqlalchemy import func
from app.database import SessionLocal
from app.models.bank_monitor import PlaidApiCall


def record(endpoint, environment, outcome):
    if os.getenv('PLAID_USAGE_TRACKING_ENABLED') != 'true':
        return
    try:
        with SessionLocal() as db:
            db.add(PlaidApiCall(endpoint=endpoint, environment=environment, outcome=outcome,
                                recorded_at=datetime.now(timezone.utc)))
            db.commit()
    except Exception:
        # Telemetry must never turn a completed provider read into a retried request.
        logging.getLogger(__name__).warning('Plaid usage record unavailable')


def summary(db, now=None):
    now = now or datetime.now(timezone.utc)
    month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    environment = os.getenv('PLAID_ENV', 'unconfigured')
    query = db.query(PlaidApiCall).filter(PlaidApiCall.environment == environment)
    first = query.with_entities(func.min(PlaidApiCall.recorded_at)).scalar()
    last = query.with_entities(func.max(PlaidApiCall.recorded_at)).scalar()
    rows = query.filter(PlaidApiCall.recorded_at >= month, PlaidApiCall.recorded_at <= now).with_entities(
        PlaidApiCall.endpoint, PlaidApiCall.outcome, func.count(PlaidApiCall.id)).group_by(
        PlaidApiCall.endpoint, PlaidApiCall.outcome).all()
    counts = {}
    for endpoint, outcome, count in rows:
        counts.setdefault(endpoint, {'endpoint': endpoint, 'calls': 0, 'successful': 0, 'failed': 0, 'unknown': 0})
        counts[endpoint]['calls'] += count
        counts[endpoint][outcome] += count
    balance = counts.get('/accounts/balance/get', {}).get('successful', 0)
    rate = None
    try:
        candidate = Decimal(os.getenv('PLAID_BALANCE_RATE_USD', ''))
        if candidate.is_finite() and candidate >= 0:
            rate = candidate
    except InvalidOperation:
        pass
    # Free sandbox traffic must not be priced using production contract rates.
    estimate = Decimal(0) if environment == 'sandbox' else balance * rate if environment == 'production' and rate is not None else None
    snapshot = None
    if environment == 'production':
        try:
            snapshot = json.loads(os.getenv('PLAID_ALLOWANCE_SNAPSHOT', 'null'))
        except (ValueError, TypeError):
            pass
    return {'allowance_snapshot': snapshot, 'scope': 'elis_integration', 'tracking_enabled': os.getenv('PLAID_USAGE_TRACKING_ENABLED') == 'true', 'environment': environment, 'period_start': month,
            'as_of': now, 'first_recorded_at': first, 'last_recorded_at': last,
            'calls': sum(r['calls'] for r in counts.values()),
            'successful_balance_reads': balance,
            'balance_rate_usd': str(rate) if rate is not None else None,
            'balance_estimate_usd': str(estimate) if estimate is not None and first else None,
            'billable_usage': None, 'invoice_total_usd': None,
            'transactions_free_exhausted_at': os.getenv('PLAID_TRANSACTIONS_FREE_EXHAUSTED_AT') if environment == 'production' else None,
            'endpoints': sorted(counts.values(), key=lambda row: (-row['calls'], row['endpoint']))}
