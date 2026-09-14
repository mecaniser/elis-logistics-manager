"""Strictly authenticated, tenant-scoped settings and read-only run history."""
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.auth_utils import SESSION_COOKIE_NAME, verify_session_token
from app.database import get_db
from app.models.tenant import Tenant
from app.models.bank_monitor import BankMonitorConfig, BankMonitorRun
from app.services.bank_monitor import MonitorRules, next_check

router = APIRouter()


def bank_tenant(request: Request, db: Session = Depends(get_db)):
    try:
        valid, username = verify_session_token(request.cookies.get(SESSION_COOKIE_NAME, ''))
    except (ValueError, TypeError):
        valid, username = False, None
    if not valid or not os.getenv('APP_AUTH_USERNAME') or username != os.getenv('APP_AUTH_USERNAME'):
        raise HTTPException(401, 'Sign in to access bank monitoring.')
    selectors = request.headers.getlist('x-tenant-id')
    if len(selectors) != 1 or not selectors[0].isascii() or not selectors[0].isdigit():
        raise HTTPException(400, 'Select one business.')
    tenant_id = int(selectors[0])
    allowed = os.getenv('BANK_MONITOR_TENANT_IDS', '').split(',')
    if tenant_id <= 0 or tenant_id > 2147483647 or str(tenant_id) not in [s.strip() for s in allowed]:
        raise HTTPException(404, 'Bank monitoring is not configured for this business.')
    if not db.query(Tenant).filter(Tenant.id == tenant_id, Tenant.is_active.is_(True)).first():
        raise HTTPException(404, 'Business unavailable.')
    return tenant_id


@router.get('')
def dashboard(tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    config = db.get(BankMonitorConfig, tenant_id)
    runs = db.query(BankMonitorRun).filter_by(tenant_id=tenant_id).order_by(BankMonitorRun.id.desc()).limit(30).all()
    return {'rules': config.rules if config else MonitorRules().model_dump(),
            'mode': 'proposal_only', 'next_check': next_check(datetime.now(timezone.utc)),
            'runs': [{'id': r.id, 'scheduled_date': r.scheduled_date, 'started_at': r.started_at,
                      'finished_at': r.finished_at, 'status': r.status, 'result': r.result} for r in runs]}


@router.put('')
def save(rules: MonitorRules, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    # Custom header forces browser cross-origin writes through CORS preflight.
    if request.headers.get('x-bank-monitor-action') != 'save-settings':
        raise HTTPException(403, 'Missing settings action header.')
    config = db.get(BankMonitorConfig, tenant_id)
    if not config:
        config = BankMonitorConfig(tenant_id=tenant_id)
        db.add(config)
    config.enabled = rules.enabled
    config.rules = rules.model_dump()
    config.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {'saved': True, 'rules': config.rules, 'mode': 'proposal_only'}
