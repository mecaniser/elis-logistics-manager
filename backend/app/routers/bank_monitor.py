"""Strictly authenticated, tenant-scoped settings and read-only run history."""
import os
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.auth_utils import SESSION_COOKIE_NAME, verify_session_token
from app.database import get_db
from app.models.tenant import Tenant
from app.models.bank_monitor import BankMonitorConfig, BankMonitorRun, BankMonitorWorkerHeartbeat
from app.services.bank_monitor import EASTERN, MonitorRules, next_check

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
    heartbeat = db.get(BankMonitorWorkerHeartbeat, tenant_id)
    now = datetime.now(timezone.utc)
    last_seen = heartbeat.last_seen_at if heartbeat else None
    if last_seen and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    worker_online = bool(last_seen and (now - last_seen).total_seconds() <= 120)
    runs = db.query(BankMonitorRun).filter_by(tenant_id=tenant_id).order_by(BankMonitorRun.id.desc()).limit(30).all()
    return {'rules': config.rules if config else MonitorRules().model_dump(),
            'mode': 'proposal_only', 'next_check': next_check(datetime.now(timezone.utc)),
            'worker': {'status': 'online' if worker_online else 'offline', 'last_seen_at': last_seen},
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


# These endpoints prepare forms only. No bank submission endpoint exists.
from uuid import uuid4
from pydantic import Field
from sqlalchemy.exc import IntegrityError
from app.services.bank_monitor import StrictModel
from app.models.bank_monitor import BankTransferDraft


class DraftInput(StrictModel):
    charge_reference: str = Field(min_length=3, max_length=120, pattern=r'^[A-Za-z0-9 .:_-]+$')
    amount_cents: int = Field(gt=0, le=100000000, strict=True)
    from_last4: str = Field(pattern=r'^[0-9]{4}$')
    to_last4: str = Field(pattern=r'^[0-9]{4}$')
    memo: str = Field(min_length=5, max_length=34, pattern=r'^Cvr [A-Za-z0-9 ._-]+$')
    bank_state: str | None = Field(default=None, pattern=r'^(posted|pending)$')
    bank_effective_date: date | None = None


def draft_json(d):
    created = d.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    result = {k: getattr(d, k) for k in ('id', 'charge_reference', 'amount_cents', 'from_last4', 'to_last4', 'memo', 'status', 'bank_state')}
    result['bank_effective_date'] = d.bank_effective_date.isoformat() if d.bank_effective_date else None
    result['bank_date'] = created.astimezone(EASTERN).date().isoformat()
    return result


def draft_action(request):
    if request.headers.get('x-bank-monitor-action') != 'reviewed-transfer':
        raise HTTPException(403, 'Missing reviewed transfer action.')


@router.get('/drafts')
def list_drafts(tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    return [draft_json(d) for d in db.query(BankTransferDraft).filter_by(tenant_id=tenant_id).order_by(BankTransferDraft.created_at.desc()).limit(100)]


@router.post('/drafts')
def create_draft(data: DraftInput, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    draft_action(request)
    config = db.get(BankMonitorConfig, tenant_id)
    if not config:
        raise HTTPException(409, 'Configure bank accounts first.')
    rules = MonitorRules.model_validate(config.rules)
    if data.from_last4 not in {a.last4 for a in rules.sources} or data.to_last4 not in {a.last4 for a in rules.checking}:
        raise HTTPException(422, 'Use a configured credit source and checking destination.')
    draft = BankTransferDraft(id=str(uuid4()), tenant_id=tenant_id, **data.model_dump(),
                              status='reviewed', created_at=datetime.now(timezone.utc))
    db.add(draft)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A draft already exists for this charge reference.') from None
    return draft_json(draft)


@router.post('/drafts/{draft_id}/prepare')
def claim_draft(draft_id: str, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    draft_action(request)
    draft = db.query(BankTransferDraft).filter_by(id=draft_id, tenant_id=tenant_id).first()
    config = db.get(BankMonitorConfig, tenant_id)
    if not draft or not config:
        raise HTTPException(409, 'Draft unavailable.')
    rules = MonitorRules.model_validate(config.rules)
    if draft.from_last4 not in {a.last4 for a in rules.sources} or draft.to_last4 not in {a.last4 for a in rules.checking}:
        raise HTTPException(409, 'Configured accounts changed. Review the draft.')
    # Reserve before browser dispatch; timeouts cannot silently reprepare a draft.
    updated = db.query(BankTransferDraft).filter_by(id=draft_id, tenant_id=tenant_id, status='reviewed').update({'status': 'preparation_requested'})
    if not updated:
        db.rollback()
        raise HTTPException(409, 'Draft unavailable or already requested. Check bank history before another attempt.')
    db.commit()
    return draft_json(db.get(BankTransferDraft, draft_id))


class DraftOutcome(StrictModel):
    status: str = Field(pattern=r'^(prepared_awaiting_submission|preparation_failed|preparation_not_started)$')


class DraftRetry(StrictModel):
    reason: str = Field(pattern=r'^signed_out_before_form$')


class DraftBankDetails(StrictModel):
    bank_state: str = Field(pattern=r'^(posted|pending)$')
    bank_effective_date: date


@router.put('/drafts/{draft_id}/bank-details')
def update_draft_bank_details(draft_id: str, data: DraftBankDetails, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    draft_action(request)
    updated = db.query(BankTransferDraft).filter_by(id=draft_id, tenant_id=tenant_id).update(data.model_dump())
    if not updated:
        db.rollback()
        raise HTTPException(404, 'Draft unavailable.')
    db.commit()
    return {'saved': True, **data.model_dump(mode='json')}


@router.post('/drafts/{draft_id}/outcome')
def draft_outcome(draft_id: str, data: DraftOutcome, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    draft_action(request)
    # Only explicit extension reports before bank-tab creation release a claim.
    # Transport failures and unknown outcomes retain the lock.
    outcome = 'reviewed' if data.status == 'preparation_not_started' else data.status
    updated = db.query(BankTransferDraft).filter_by(id=draft_id, tenant_id=tenant_id, status='preparation_requested').update({'status': outcome})
    if not updated:
        db.rollback()
        raise HTTPException(409, 'Draft state changed; refresh the queue.')
    db.commit()
    return {'status': outcome, 'transfers_executed': False}


@router.post('/drafts/{draft_id}/retry')
def retry_draft(draft_id: str, data: DraftRetry, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    draft_action(request)
    updated = db.query(BankTransferDraft).filter_by(
        id=draft_id, tenant_id=tenant_id, status='preparation_failed').update({'status': 'reviewed'})
    if not updated:
        db.rollback()
        raise HTTPException(409, 'Only a failed preparation can be resumed.')
    db.commit()
    return {'status': 'reviewed', 'reason': data.reason, 'transfers_executed': False}


class HistoryEvidence(StrictModel):
    source: str = Field(pattern=r'^[a-f0-9]{64}$')
    destination: str = Field(pattern=r'^[a-f0-9]{64}$')


@router.post('/drafts/{draft_id}/history-match')
def history_match(draft_id: str, evidence: HistoryEvidence, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    draft_action(request)
    if evidence.source == evidence.destination:
        raise HTTPException(422, 'Separate source and destination history evidence is required.')
    # Evidence is reported by the signed-in user's extension, not a server bank API.
    try:
        updated = db.query(BankTransferDraft).filter(BankTransferDraft.id == draft_id,
            BankTransferDraft.tenant_id == tenant_id,
            BankTransferDraft.status.in_(['preparation_requested', 'prepared_awaiting_submission', 'preparation_failed'])).update({'status': 'bank_history_matched', 'source_evidence': evidence.source, 'destination_evidence': evidence.destination})
        if not updated:
            db.rollback()
            raise HTTPException(409, 'Draft is not awaiting verification.')
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Bank evidence is already associated with another draft.') from None
    return {'status': 'bank_history_matched', 'verification_source': 'user_browser_extension'}
