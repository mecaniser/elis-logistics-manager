"""Strictly authenticated, tenant-scoped settings and read-only run history."""
import os
import hashlib
import json
from uuid import uuid4
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.auth_utils import SESSION_COOKIE_NAME, verify_session_token
from app.database import get_db
from app.models.tenant import Tenant
from app.models.bank_monitor import (BankMonitorConfig, BankMonitorConnectionCheck, BankMonitorBrowserCheck,
                                     BankMonitorRun, BankMonitorWorkerHeartbeat, BankRepaymentRun,
                                     BankProviderConnection, BankProviderLinkAttempt)
from app.services.bank_monitor import (AccountBalance, BalanceSnapshot, EASTERN,
                                       MonitorRules, StrictModel,
                                       calculate, calculate_repayment, due_date, next_check)
from app.services import plaid_bank
from app.services.bank_transfer_review import build_review

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
    connection_check = db.query(BankMonitorConnectionCheck).filter_by(tenant_id=tenant_id).order_by(BankMonitorConnectionCheck.id.desc()).first()
    browser_check = db.query(BankMonitorBrowserCheck).filter_by(tenant_id=tenant_id).order_by(BankMonitorBrowserCheck.id.desc()).first()
    repayment_runs = db.query(BankRepaymentRun).filter_by(tenant_id=tenant_id).order_by(BankRepaymentRun.id.desc()).limit(30).all()
    provider = db.get(BankProviderConnection, tenant_id)
    reader_mode = os.getenv('BANK_MONITOR_READER_MODE', 'private_worker')
    return {'rules': config.rules if config else MonitorRules().model_dump(),
            'reader_mode': reader_mode if reader_mode in {'signed_in_chrome', 'plaid'} else 'private_worker',
            'provider_connection': {
                'configured': plaid_bank.configured(), 'linked': bool(provider),
                'status': provider.status if provider else 'not_linked',
                'last_checked_at': provider.last_checked_at if provider else None,
                'last_error': provider.last_error if provider else None,
                'accounts': sorted(provider.account_map.keys()) if provider else [],
            },
            'mode': 'proposal_only', 'next_check': next_check(datetime.now(timezone.utc)),
            'worker': {'status': 'online' if worker_online else 'offline', 'last_seen_at': last_seen},
            'connection_check': ({'id': connection_check.id, 'status': connection_check.status,
                                  'requested_at': connection_check.requested_at,
                                  'finished_at': connection_check.finished_at,
                                  'result': connection_check.result} if connection_check else None),
            'browser_check': ({'id': browser_check.id, 'observed_at': browser_check.observed_at,
                               'status': browser_check.status, 'result': browser_check.result} if browser_check else None),
            'runs': [{'id': r.id, 'scheduled_date': r.scheduled_date, 'started_at': r.started_at,
                      'finished_at': r.finished_at, 'status': r.status, 'result': r.result} for r in runs],
            'repayment_runs': [{'id': r.id, 'started_at': r.started_at,
                                'finished_at': r.finished_at, 'status': r.status,
                                'result': r.result} for r in repayment_runs]}


def provider_action(request: Request, action: str):
    if request.headers.get('x-bank-monitor-action') != action:
        raise HTTPException(403, 'Missing bank connection action header.')
    if not plaid_bank.configured():
        raise HTTPException(409, 'Bank connection provider is not configured.')
    if plaid_bank.environment() != 'production':
        raise HTTPException(409, 'Production bank provider access is required.')


class ProviderLinkRequest(StrictModel):
    """Plaid Link handles bank credentials and consent outside ELIS."""


@router.post('/provider/link-token')
def create_provider_link_token(data: ProviderLinkRequest, request: Request,
                               tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    provider_action(request, 'start-provider-link')
    if db.get(BankProviderConnection, tenant_id):
        raise HTTPException(409, 'Bank connection already exists. Use reconnect to renew access.')
    config = db.get(BankMonitorConfig, tenant_id)
    if not config:
        raise HTTPException(409, 'Configure monitored accounts before connecting the bank.')
    rules = MonitorRules.model_validate(config.rules)
    if not rules.checking or not rules.sources:
        raise HTTPException(409, 'Configure checking and funding accounts first.')
    try:
        token = plaid_bank.link_token(tenant_id)
    except plaid_bank.PlaidBankError as exc:
        raise HTTPException(503, str(exc)) from None
    now = datetime.now(timezone.utc)
    attempt = BankProviderLinkAttempt(id=str(uuid4()), tenant_id=tenant_id,
                                      token_hash=hashlib.sha256(token.encode()).hexdigest(),
                                      expires_at=now + timedelta(hours=1))
    db.add(attempt)
    db.commit()
    return {'link_token': token, 'attempt_id': attempt.id}


class ProviderExchangeInput(StrictModel):
    link_token: str
    attempt_id: str
    public_token: str


@router.post('/provider/exchange')
def exchange_provider_token(data: ProviderExchangeInput, request: Request,
                            tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    provider_action(request, 'finish-provider-link')
    attempt = db.query(BankProviderLinkAttempt).filter_by(id=data.attempt_id, tenant_id=tenant_id).with_for_update().one_or_none()
    now = datetime.now(timezone.utc)
    if not attempt or attempt.consumed_at or attempt.token_hash != hashlib.sha256(data.link_token.encode()).hexdigest() or (
            attempt.expires_at.replace(tzinfo=timezone.utc) if attempt.expires_at.tzinfo is None else attempt.expires_at) < now:
        raise HTTPException(409, 'Bank connection session expired. Start again.')
    attempt.consumed_at = now
    db.commit()
    config = db.query(BankMonitorConfig).filter_by(tenant_id=tenant_id).with_for_update().one_or_none()
    if not config:
        raise HTTPException(409, 'Configure monitored accounts first.')
    if db.get(BankProviderConnection, tenant_id):
        raise HTTPException(409, 'Bank connection already exists. Use reconnect to renew access.')
    rules = MonitorRules.model_validate(config.rules)
    try:
        access_token, item_id = plaid_bank.exchange(data.public_token)
        bank_item = plaid_bank.item(access_token)
        if bank_item.get('item_id') != item_id or bank_item.get('institution_id') != plaid_bank.TRULIANT_INSTITUTION_ID:
            raise plaid_bank.PlaidBankError('provider_institution_mismatch')
        accounts = plaid_bank.real_time_accounts(access_token)
        account_map = plaid_bank.map_accounts(accounts, rules)
        plaid_bank.balance_snapshot(access_token, rules, account_map, now, accounts)
        encrypted = plaid_bank.encrypt_token(access_token)
    except plaid_bank.PlaidBankError as exc:
        raise HTTPException(422, str(exc)) from None
    db.add(BankProviderConnection(tenant_id=tenant_id, provider='plaid', item_id=item_id,
                                  institution_id=plaid_bank.TRULIANT_INSTITUTION_ID,
                                  encrypted_access_token=encrypted, account_map=account_map,
                                  status='linked_unverified', linked_at=now))
    db.commit()
    return {'linked': True, 'accounts': sorted(account_map.keys()), 'status': 'linked_unverified'}


@router.post('/provider/update-link-token')
def create_provider_update_token(data: ProviderLinkRequest, request: Request,
                                 tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    provider_action(request, 'renew-provider-link')
    provider = db.get(BankProviderConnection, tenant_id)
    if not provider:
        raise HTTPException(409, 'Connect the bank first.')
    try:
        token = plaid_bank.link_token(tenant_id, access_token=plaid_bank.decrypt_token(provider.encrypted_access_token))
    except plaid_bank.PlaidBankError as exc:
        raise HTTPException(503, str(exc)) from None
    return {'link_token': token}


@router.post('/provider/renewed')
def confirm_provider_renewal(data: ProviderLinkRequest, request: Request,
                             tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    provider_action(request, 'confirm-provider-renewal')
    provider = db.get(BankProviderConnection, tenant_id)
    config = db.get(BankMonitorConfig, tenant_id)
    if not provider or not config:
        raise HTTPException(409, 'Bank connection and monitored accounts are required.')
    rules = MonitorRules.model_validate(config.rules)
    try:
        token = plaid_bank.decrypt_token(provider.encrypted_access_token)
        bank_item = plaid_bank.item(token)
        if bank_item.get('item_id') != provider.item_id or bank_item.get('institution_id') != plaid_bank.TRULIANT_INSTITUTION_ID:
            raise plaid_bank.PlaidBankError('provider_institution_mismatch')
        accounts = plaid_bank.real_time_accounts(token)
        account_map = plaid_bank.map_accounts(accounts, rules)
        plaid_bank.balance_snapshot(token, rules, account_map, datetime.now(timezone.utc), accounts)
    except plaid_bank.PlaidBankError as exc:
        raise HTTPException(422, str(exc)) from None
    provider.account_map = account_map
    provider.status = 'linked_unverified'
    provider.last_error = None
    db.commit()
    return {'linked': True, 'status': 'linked_unverified', 'accounts': sorted(account_map.keys())}


@router.get('/provider/accounts')
def provider_accounts(request: Request, tenant_id: int = Depends(bank_tenant),
                      db: Session = Depends(get_db)):
    provider_action(request, 'discover-provider-accounts')
    provider = db.get(BankProviderConnection, tenant_id)
    if not provider:
        raise HTTPException(409, 'Connect Truliant through Plaid first.')
    try:
        token = plaid_bank.decrypt_token(provider.encrypted_access_token)
        bank_item = plaid_bank.item(token)
        if bank_item.get('item_id') != provider.item_id or bank_item.get('institution_id') != plaid_bank.TRULIANT_INSTITUTION_ID:
            raise plaid_bank.PlaidBankError('provider_institution_mismatch')
        accounts = plaid_bank.discover_accounts(token)
    except plaid_bank.PlaidBankError as exc:
        raise HTTPException(422, str(exc)) from None
    return {'accounts': accounts}


class ConnectionCheckInput(StrictModel):
    """The request cannot carry a username, password, or MFA code."""


@router.post('/connection-checks', status_code=202)
def request_connection_check(data: ConnectionCheckInput, request: Request, tenant_id: int = Depends(bank_tenant),
                             db: Session = Depends(get_db)):
    """Ask the private worker for one read-only account check; never accept secrets."""
    if request.headers.get('x-bank-monitor-action') != 'verify-worker-bank-access':
        raise HTTPException(403, 'Missing bank verification action header.')
    if os.getenv('BANK_MONITOR_READER_MODE') == 'signed_in_chrome' and not db.get(BankProviderConnection, tenant_id):
        raise HTTPException(409, 'Connect Truliant through Plaid before requesting a server read.')
    # Serialize requests for this tenant so two clicks cannot queue two logins.
    config = db.query(BankMonitorConfig).filter_by(tenant_id=tenant_id).with_for_update().one_or_none()
    if not config:
        raise HTTPException(409, 'Configure monitored bank accounts first.')
    rules = MonitorRules.model_validate(config.rules)
    if not rules.checking or not rules.sources:
        raise HTTPException(409, 'Configure checking and funding accounts first.')
    now = datetime.now(timezone.utc)
    heartbeat = db.get(BankMonitorWorkerHeartbeat, tenant_id)
    if not heartbeat:
        raise HTTPException(409, 'The private bank worker is offline.')
    seen = heartbeat.last_seen_at.replace(tzinfo=timezone.utc) if heartbeat.last_seen_at.tzinfo is None else heartbeat.last_seen_at
    if now - seen > timedelta(seconds=120):
        raise HTTPException(409, 'The private bank worker is offline.')
    latest = db.query(BankMonitorConnectionCheck).filter_by(tenant_id=tenant_id).order_by(BankMonitorConnectionCheck.id.desc()).first()
    if latest and latest.status in ('pending', 'running'):
        raise HTTPException(409, 'A bank connection check is already in progress.')
    if latest:
        requested = latest.requested_at.replace(tzinfo=timezone.utc) if latest.requested_at.tzinfo is None else latest.requested_at
        if now - requested < timedelta(minutes=2):
            raise HTTPException(429, 'Wait two minutes before requesting another bank connection check.')
    check = BankMonitorConnectionCheck(tenant_id=tenant_id, requested_at=now,
                                       status='pending', result={'transfers_executed': False})
    db.add(check)
    db.commit()
    db.refresh(check)
    return {'id': check.id, 'status': check.status}


class BrowserCheckInput(StrictModel):
    """Only explicit account values; no cookies, credentials, or raw bank HTML."""
    snapshot: BalanceSnapshot
    histories_verified: list[str]


@router.post('/browser-checks')
def record_browser_check(data: BrowserCheckInput, request: Request,
                         tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    if request.headers.get('x-bank-monitor-action') != 'record-browser-check':
        raise HTTPException(403, 'Missing browser check action header.')
    config = db.get(BankMonitorConfig, tenant_id)
    if not config:
        raise HTTPException(409, 'Configure bank monitoring first.')
    rules = MonitorRules.model_validate(config.rules)
    required = {account.last4 for account in rules.checking + rules.sources}
    observed = {account.last4 for account in data.snapshot.accounts}
    histories = data.histories_verified
    if observed != required or len(histories) != len(set(histories)) or set(histories) != {a.last4 for a in rules.checking}:
        raise HTTPException(422, 'Every configured account and checking history must be verified.')
    now = datetime.now(timezone.utc)
    try:
        result = calculate(rules, data.snapshot, now)
    except ValueError:
        raise HTTPException(422, 'The bank snapshot is incomplete or stale; no check was recorded.') from None
    result['source'] = 'signed_in_chrome_assistant'
    browser_check = BankMonitorBrowserCheck(tenant_id=tenant_id, observed_at=data.snapshot.observed_at,
                                            received_at=now, status=result['status'], result=result)
    db.add(browser_check)
    scheduled_run = None
    local = now.astimezone(EASTERN)
    # A browser read is a scheduled run only when captured near the actual slot.
    if rules.enabled and due_date(now) == local.date() and local.hour == 17 and local.minute < 45:
        existing = db.query(BankMonitorRun).filter_by(tenant_id=tenant_id, scheduled_date=local.date()).with_for_update().first()
        if existing and (existing.status in {'bank_read_failed', 'bank_security_challenge', 'chrome_check_missed'}
                         or existing.result.get('source') == 'plaid_background'
                         or (os.getenv('BANK_MONITOR_READER_MODE') == 'signed_in_chrome'
                             and existing.status == 'running')):
            # A complete same-slot Chrome result supersedes a provisional Plaid
            # result, including one still running. Never rewrite a prior day.
            existing.status = result['status']
            existing.result = result
            existing.finished_at = now
            scheduled_run = existing
        elif not existing:
            scheduled_run = BankMonitorRun(tenant_id=tenant_id, scheduled_date=local.date(),
                                           started_at=now, finished_at=now, status=result['status'], result=result)
            db.add(scheduled_run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'A check for this scheduled time was already recorded.') from None
    db.refresh(browser_check)
    return {'id': browser_check.id, 'status': browser_check.status,
            'scheduled_run_id': scheduled_run.id if scheduled_run else None,
            'observed_at': browser_check.observed_at, 'transfers_executed': False}


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
from app.models.bank_monitor import BankTransferDraft


def rules_hash(rules):
    return hashlib.sha256(json.dumps(rules.model_dump(), sort_keys=True).encode()).hexdigest()


def unfinished_drafts(db, tenant_id):
    return db.query(BankTransferDraft).filter(BankTransferDraft.tenant_id == tenant_id,
        BankTransferDraft.status.notin_(['bank_history_matched', 'cancelled'])).all()


def fresh_review_read(db, tenant_id, rules):
    from app.bank_monitor_worker import read_provider, provider_visibility
    try:
        snapshot = read_provider(db, tenant_id, rules, datetime.now(timezone.utc))
        visibility = provider_visibility(db, tenant_id)
    except plaid_bank.PlaidBankError as exc:
        db.commit()  # Preserve the connection's actionable error state.
        raise HTTPException(409, f'Bank refresh stopped: {str(exc)}. Renew bank access or try again.') from None
    return snapshot, visibility


@router.post('/transfer-reviews')
def create_transfer_review(data: ConnectionCheckInput, request: Request,
                           tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    provider_action(request, 'review-bank-transfers')
    config = db.query(BankMonitorConfig).filter_by(tenant_id=tenant_id).with_for_update().one_or_none()
    if not config:
        raise HTTPException(409, 'Configure bank accounts first.')
    rules = MonitorRules.model_validate(config.rules)
    snapshot, visibility = fresh_review_read(db, tenant_id, rules)
    result = build_review(rules, snapshot, visibility, unfinished_drafts(db, tenant_id))
    if not rules.repayment.priority:
        result['issues'].append('Choose a credit repayment priority in monitoring settings to include credit repayments.')
    result.update({'snapshot': snapshot.model_dump(mode='json'), 'visibility': visibility,
                   'rules_hash': rules_hash(rules), 'item_id': db.get(BankProviderConnection, tenant_id).item_id})
    now = datetime.now(timezone.utc)
    run = BankRepaymentRun(tenant_id=tenant_id, started_at=snapshot.observed_at, finished_at=now,
                           status='review_required', result=result)
    db.add(run)
    # Keep the overview on the exact same fresh read as the review.
    from app.services.bank_cash_plan import calculate_cash_plan
    db.add(BankMonitorConnectionCheck(tenant_id=tenant_id, requested_at=snapshot.observed_at,
        started_at=snapshot.observed_at, finished_at=now, status='balance_only', result={
            'source': 'plaid', 'observed_at': snapshot.observed_at.isoformat(),
            'accounts': [a.model_dump(mode='json') for a in snapshot.accounts],
            'transaction_visibility': visibility, 'cash_plan': calculate_cash_plan(rules, snapshot, visibility),
            'transfers_executed': False}))
    db.commit()
    return {'id': run.id, 'result': result, 'expires_at': (snapshot.observed_at + timedelta(minutes=5)).isoformat()}


class ReviewedRoute(StrictModel):
    from_last4: str = Field(pattern=r'^\d{4}$')
    to_last4: str = Field(pattern=r'^\d{4}$')
    amount_cents: int = Field(gt=0, le=100000000, strict=True)


class ReviewedRoutes(StrictModel):
    routes: list[ReviewedRoute] = Field(min_length=1, max_length=100)


@router.post('/transfer-reviews/{run_id}/drafts')
def create_reviewed_drafts(run_id: int, data: ReviewedRoutes, request: Request,
                           tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    provider_action(request, 'create-reviewed-transfers')
    config = db.query(BankMonitorConfig).filter_by(tenant_id=tenant_id).with_for_update().one_or_none()
    run = db.query(BankRepaymentRun).filter_by(id=run_id, tenant_id=tenant_id).with_for_update().one_or_none()
    provider = db.get(BankProviderConnection, tenant_id)
    if not config or not run or not provider or run.result.get('source') != 'plaid_review':
        raise HTTPException(409, 'Transfer review is unavailable. Refresh bank data.')
    result = dict(run.result)
    if result.get('drafts_created'):
        raise HTTPException(409, 'These transfers are already in the queue.')
    rules = MonitorRules.model_validate(config.rules)
    snapshot = BalanceSnapshot.model_validate(result['snapshot'])
    now = datetime.now(timezone.utc)
    if not -30 <= (now - snapshot.observed_at).total_seconds() <= 300:
        raise HTTPException(409, 'This bank read expired. Refresh the review before creating drafts.')
    if result['rules_hash'] != rules_hash(rules) or result['item_id'] != provider.item_id:
        raise HTTPException(409, 'Accounts or settings changed. Refresh the review.')
    current = build_review(rules, snapshot, result['visibility'], unfinished_drafts(db, tenant_id))
    limits = {(p['from_last4'], p['to_last4']): p for p in current['proposals']}
    original = {(p['from_last4'], p['to_last4']): p for p in result['proposals']}
    seen, created = set(), []
    for index, route in enumerate(data.routes, 1):
        key = (route.from_last4, route.to_last4)
        if key in seen or key not in limits or key not in original or route.amount_cents > min(limits[key]['amount_cents'], original[key]['amount_cents']):
            raise HTTPException(409, 'A route or amount exceeds this review. Refresh to include changes to the queue.')
        seen.add(key)
        prefix = 'Rpy' if limits[key]['kind'] == 'repayment' else 'Cvr'
        draft = BankTransferDraft(id=str(uuid4()), tenant_id=tenant_id,
            charge_reference=f'bank-review-{run.id}-{index}', **route.model_dump(),
            memo=f'{prefix} {route.to_last4} {now.astimezone(EASTERN):%m%d} {run.id}-{index}',
            status='reviewed', created_at=now)
        db.add(draft)
        created.append(draft)
    run.result = {**result, 'drafts_created': True, 'draft_ids': [d.id for d in created],
                  'proposals': [r.model_dump() for r in data.routes]}
    db.commit()
    return {'created': len(created), 'drafts': [draft_json(d) for d in created], 'transfers_executed': False}


class RepaymentCheckingEvidence(StrictModel):
    last4: str = Field(pattern=r'^\d{4}$')
    current_cents: int = Field(ge=-100000000, le=100000000, strict=True)
    pending_debits_cents: int = Field(ge=0, le=100000000, strict=True)
    settled_cash_cents: int = Field(ge=0, le=100000000, strict=True)
    eligible_income_cents: int = Field(ge=0, le=100000000, strict=True)
    income_date: date


class RepaymentSourceEvidence(StrictModel):
    last4: str = Field(pattern=r'^\d{4}$')
    payoff_cents: int = Field(ge=0, le=100000000, strict=True)


class ManualRepaymentInput(StrictModel):
    checking: list[RepaymentCheckingEvidence] = Field(min_length=1, max_length=10)
    sources: list[RepaymentSourceEvidence] = Field(min_length=1, max_length=5)
    evidence_confirmed: bool = Field(strict=True)
    funding_basis: Literal['cleared_income', 'verified_cash'] = 'cleared_income'


@router.post('/repayment-runs')
def run_repayment_now(data: ManualRepaymentInput, request: Request,
                      tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    if request.headers.get('x-bank-monitor-action') != 'run-repayment-check':
        raise HTTPException(403, 'Missing repayment check action header.')
    if data.evidence_confirmed is not True:
        raise HTTPException(422, 'Confirm that the evidence was checked against current bank records.')
    config = db.get(BankMonitorConfig, tenant_id)
    if not config:
        raise HTTPException(409, 'Configure bank monitoring first.')
    rules = MonitorRules.model_validate(config.rules)
    if not rules.repayment.enabled:
        raise HTTPException(409, 'Enable repayment proposals in Monitoring settings first.')
    expected_checking = {account.last4 for account in rules.checking}
    expected_sources = set(rules.repayment.priority)
    supplied_checking = [account.last4 for account in data.checking]
    supplied_sources = [account.last4 for account in data.sources]
    if len(supplied_checking) != len(set(supplied_checking)) or set(supplied_checking) != expected_checking:
        raise HTTPException(422, 'Provide evidence for every configured checking account exactly once.')
    if len(supplied_sources) != len(set(supplied_sources)) or set(supplied_sources) != expected_sources:
        raise HTTPException(422, 'Provide payoff evidence for every repayment source exactly once.')
    for account in data.checking:
        if account.eligible_income_cents > account.settled_cash_cents:
            label = 'Cash chosen for repayment' if data.funding_basis == 'verified_cash' else 'Incoming funds'
            raise HTTPException(422, f'{label} for checking account ••{account.last4} cannot exceed cash available after pending debits.')
    now = datetime.now(timezone.utc)
    accounts = [AccountBalance(**account.model_dump()) for account in data.checking]
    accounts.extend(AccountBalance(**account.model_dump()) for account in data.sources)
    snapshot = BalanceSnapshot(observed_at=now, accounts=accounts)
    result = calculate_repayment(rules, snapshot, now, require_friday=False)
    # The calculation uses eligible_income_cents as its per-account cap. For an
    # on-demand verified-cash run that cap is the cash the user chose to repay;
    # scheduled Friday runs continue to require same-day income evidence.
    result.update({'source': 'manual', 'funding_basis': data.funding_basis, 'observed_at': now.isoformat(),
                   'evidence_confirmed': True,
                   'checking_evidence': [account.model_dump(mode='json') for account in data.checking],
                   'source_evidence': [account.model_dump(mode='json') for account in data.sources]})
    run = BankRepaymentRun(tenant_id=tenant_id, started_at=now, finished_at=now,
                           status=result['status'], result=result)
    db.add(run)
    db.commit()
    db.refresh(run)
    return {'id': run.id, 'started_at': run.started_at, 'finished_at': run.finished_at,
            'status': run.status, 'result': run.result}


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
    result['kind'] = 'repayment' if d.memo.startswith('Rpy ') else 'coverage'
    return result


def draft_action(request):
    if request.headers.get('x-bank-monitor-action') != 'reviewed-transfer':
        raise HTTPException(403, 'Missing reviewed transfer action.')


@router.get('/drafts')
def list_drafts(tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    return [draft_json(d) for d in db.query(BankTransferDraft).filter_by(tenant_id=tenant_id).filter(BankTransferDraft.status != 'cancelled').order_by(BankTransferDraft.created_at.desc()).limit(100)]


@router.post('/drafts/{draft_id}/cancel')
def cancel_unprepared_draft(draft_id: str, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    draft_action(request)
    updated = db.query(BankTransferDraft).filter_by(id=draft_id, tenant_id=tenant_id, status='reviewed').filter(BankTransferDraft.charge_reference.like('bank-review-%')).update({'status': 'cancelled'})
    if not updated:
        db.rollback()
        raise HTTPException(409, 'Only a draft that has not started preparation can be removed.')
    db.commit()
    return {'status': 'cancelled', 'transfers_executed': False}


@router.post('/drafts')
def create_draft(data: DraftInput, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    draft_action(request)
    config = db.get(BankMonitorConfig, tenant_id)
    if not config:
        raise HTTPException(409, 'Configure bank accounts first.')
    rules = MonitorRules.model_validate(config.rules)
    if data.memo.startswith('Rpy '):
        raise HTTPException(422, 'Repayment drafts must come from a reviewed repayment run.')
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


@router.post('/repayment-runs/{run_id}/drafts')
def create_repayment_drafts(run_id: int, request: Request,
                            tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    if request.headers.get('x-bank-monitor-action') != 'create-repayment-drafts':
        raise HTTPException(403, 'Missing repayment draft action header.')
    run = db.query(BankRepaymentRun).filter_by(id=run_id, tenant_id=tenant_id).first()
    config = db.get(BankMonitorConfig, tenant_id)
    if not run or not config or run.status != 'review_required':
        raise HTTPException(409, 'Repayment proposal is unavailable.')
    result = dict(run.result or {})
    if result.get('source') == 'plaid_review':
        raise HTTPException(409, 'Open transfer review to create these drafts.')
    if result.get('drafts_created'):
        raise HTTPException(409, 'This repayment proposal is already in the transfer queue.')
    unresolved = db.query(BankTransferDraft).filter(
        BankTransferDraft.tenant_id == tenant_id,
        BankTransferDraft.memo.like('Rpy %'),
        BankTransferDraft.status.notin_(['bank_history_matched', 'cancelled'])).first()
    if unresolved:
        raise HTTPException(409, 'Finish the existing repayment transfer before adding another repayment proposal.')
    rules = MonitorRules.model_validate(config.rules)
    checking = {account.last4 for account in rules.checking}
    sources = set(rules.repayment.priority)
    created = []
    now = datetime.now(timezone.utc)
    for index, proposal in enumerate(result.get('proposals') or [], start=1):
        if proposal.get('from_last4') not in checking or proposal.get('to_last4') not in sources:
            raise HTTPException(409, 'Configured repayment accounts changed. Run the check again.')
        memo = f"Rpy {proposal['to_last4']} {now.astimezone(EASTERN):%m%d} {run.id}-{index}"
        draft = BankTransferDraft(id=str(uuid4()), tenant_id=tenant_id,
            charge_reference=f'repayment-{run.id}-{index}', amount_cents=proposal['amount_cents'],
            from_last4=proposal['from_last4'], to_last4=proposal['to_last4'], memo=memo,
            status='reviewed', created_at=now)
        db.add(draft)
        created.append(draft)
    if not created:
        raise HTTPException(409, 'This repayment proposal has no transfers to prepare.')
    result['drafts_created'] = True
    result['draft_ids'] = [draft.id for draft in created]
    run.result = result
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This repayment proposal is already in the transfer queue.') from None
    return {'created': len(created), 'drafts': [draft_json(draft) for draft in created],
            'transfers_executed': False}


@router.post('/drafts/{draft_id}/prepare')
def claim_draft(draft_id: str, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    draft_action(request)
    draft = db.query(BankTransferDraft).filter_by(id=draft_id, tenant_id=tenant_id).first()
    config = db.query(BankMonitorConfig).filter_by(tenant_id=tenant_id).with_for_update().one_or_none()
    if not draft or not config:
        raise HTTPException(409, 'Draft unavailable.')
    rules = MonitorRules.model_validate(config.rules)
    coverage_route = (draft.from_last4 in {a.last4 for a in rules.sources} and
                      draft.to_last4 in {a.last4 for a in rules.checking} and draft.memo.startswith('Cvr '))
    repayment_route = (draft.from_last4 in {a.last4 for a in rules.checking} and
                       draft.to_last4 in set(rules.repayment.priority) and draft.memo.startswith('Rpy '))
    checking_route = (draft.charge_reference.startswith('bank-review-') and
                      draft.from_last4 != draft.to_last4 and draft.memo.startswith('Cvr ') and
                      {draft.from_last4, draft.to_last4}.issubset({a.last4 for a in rules.checking}))
    if not coverage_route and not repayment_route and not checking_route:
        raise HTTPException(409, 'Configured accounts changed. Review the draft.')
    if draft.charge_reference.startswith('bank-review-'):
        if draft.status != 'reviewed':
            raise HTTPException(409, 'This draft has already been requested. Check its posting status.')
        snapshot, visibility = fresh_review_read(db, tenant_id, rules)
        review = build_review(rules, snapshot, visibility,
            [d for d in unfinished_drafts(db, tenant_id) if d.id != draft.id])
        source = next((a for a in review['cash_accounts'] if a['last4'] == draft.from_last4), None)
        destination = next((a for a in review['credit_accounts' if repayment_route else 'cash_accounts'] if a['last4'] == draft.to_last4), None)
        cap = destination.get('remaining_cents' if repayment_route else 'shortfall_cents') if destination else None
        checking_blocked = repayment_route and any(a['shortfall_cents'] is None or a['shortfall_cents'] > 0 for a in review['cash_accounts'])
        if checking_blocked or source is None or source['limit_cents'] is None or cap is None or draft.amount_cents > min(source['limit_cents'], cap):
            raise HTTPException(409, 'Bank balances changed and no longer cover this draft. Refresh the transfer review.')
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


class PlaidMatchInput(StrictModel):
    confirm: bool = False
    automatic: bool = False
    source_evidence: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    destination_evidence: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')


@router.post('/drafts/{draft_id}/plaid-match')
def plaid_match(draft_id: str, data: PlaidMatchInput, request: Request,
                tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    """Offer an exact posted pair for explicit review, then recheck before marking it."""
    provider_action(request, 'verify-plaid-transfer')
    draft = db.query(BankTransferDraft).filter_by(id=draft_id, tenant_id=tenant_id).first()
    provider = db.get(BankProviderConnection, tenant_id)
    if not draft or draft.status not in {'prepared_awaiting_submission', 'preparation_failed'} or not provider:
        raise HTTPException(409, 'A prepared transfer and active bank connection are required.')
    try:
        token = plaid_bank.decrypt_token(provider.encrypted_access_token)
        bank_item = plaid_bank.item(token)
        if bank_item.get('item_id') != provider.item_id or bank_item.get('institution_id') != plaid_bank.TRULIANT_INSTITUTION_ID:
            raise plaid_bank.PlaidBankError('provider_institution_mismatch')
        created = draft.created_at.replace(tzinfo=timezone.utc) if draft.created_at.tzinfo is None else draft.created_at
        match = plaid_bank.transfer_match(token, provider.account_map,
            from_last4=draft.from_last4, to_last4=draft.to_last4,
            amount_cents=draft.amount_cents, earliest=created.astimezone(EASTERN).date(),
            memo=draft.memo if draft.charge_reference.startswith('bank-review-') else None)
    except plaid_bank.PlaidBankError as exc:
        raise HTTPException(422, str(exc)) from None
    if match['status'] != 'ready_for_confirmation':
        if data.confirm:
            raise HTTPException(409, 'Both unique posted entries are no longer available. Review the transfer again.')
        return match
    source = match['source']
    destination = match['destination']
    source_evidence = hashlib.sha256(f"plaid:{provider.item_id}:{source['transaction_id']}".encode()).hexdigest()
    destination_evidence = hashlib.sha256(f"plaid:{provider.item_id}:{destination['transaction_id']}".encode()).hexdigest()
    if source_evidence == destination_evidence:
        raise HTTPException(409, 'Separate bank entries are required.')
    automatic_match = data.automatic and match.get('reference_matched') is True
    if data.confirm or automatic_match:
        if not automatic_match and (data.source_evidence != source_evidence or data.destination_evidence != destination_evidence):
            raise HTTPException(409, 'Bank entries changed. Review the transfer again.')
        try:
            updated = db.query(BankTransferDraft).filter(
                BankTransferDraft.id == draft_id, BankTransferDraft.tenant_id == tenant_id,
                BankTransferDraft.status.in_(['prepared_awaiting_submission', 'preparation_failed'])).update({
                    'status': 'bank_history_matched', 'source_evidence': source_evidence,
                    'destination_evidence': destination_evidence})
            if not updated:
                db.rollback()
                raise HTTPException(409, 'Transfer status changed. Refresh the queue.')
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Bank entries are already associated with another transfer.') from None
        return {'status': 'bank_history_matched', 'verification_source': 'plaid_reference_match' if automatic_match else 'plaid_confirmed_by_user'}
    return {'status': 'ready_for_confirmation',
            'source': {key: source[key] for key in ('description', 'date', 'amount_cents')},
            'destination': {key: destination[key] for key in ('description', 'date', 'amount_cents')},
            'source_evidence': source_evidence, 'destination_evidence': destination_evidence}
