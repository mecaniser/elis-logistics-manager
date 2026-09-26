"""Multiple independent bank logins and explicitly reviewed transfer routes."""
import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models.bank_monitor import (BankProfile, BankProfileAccount, BankAccountIdentity, BankProfileRoute,
    BankProfileDraft, BankProfileLink, BankProfileRun, BankMonitorConfig, BankRepaymentRun, BankTransferDraft)
from app.routers.bank_monitor import bank_tenant, provider_action, draft_json
from app.services.bank_monitor import StrictModel
from app.services import bank_profiles as profiles, plaid_bank

router = APIRouter()


def action(request):
    provider_action(request, 'manage-bank-profiles')


def lock(db, tenant_id):
    if not db.query(BankMonitorConfig).filter_by(tenant_id=tenant_id).with_for_update().first():
        raise HTTPException(409, 'Configure bank monitoring first.')


def sync(db, profile):
    try:
        profiles.sync_profile(db, profile)
    except plaid_bank.PlaidBankError as exc:
        db.commit()  # Preserve failure status without erasing the last successful timestamp.
        raise HTTPException(422, str(exc)) from None


def view(db, tenant_id):
    result = []
    for p in db.query(BankProfile).filter_by(tenant_id=tenant_id).order_by(BankProfile.created_at):
        accounts = []
        for a in db.query(BankProfileAccount).filter_by(profile_id=p.id, active=True):
            candidates = db.query(BankAccountIdentity).filter_by(tenant_id=tenant_id,
                institution_id=p.institution_id, last4=a.last4, kind=a.kind).all() if not a.account_id else []
            canonical = db.get(BankAccountIdentity, a.account_id) if a.account_id else None
            accounts.append({'id': a.id, 'account_id': a.account_id, 'name': a.name, 'last4': a.last4,
                'kind': a.kind, 'subtype': a.subtype, 'balance': a.balance,
                'reserve_cents': canonical.reserve_cents if canonical else 0,
                'overlap_candidates': [{'id': c.id, 'name': c.name, 'last4': c.last4, 'profiles': [p.name for p in db.query(BankProfile).join(BankProfileAccount, BankProfileAccount.profile_id == BankProfile.id).filter(BankProfileAccount.account_id == c.id, BankProfile.tenant_id == tenant_id)]} for c in candidates]})
        result.append({'id': p.id, 'name': p.name, 'institution_id': p.institution_id,
            'legacy': p.legacy, 'status': p.status, 'last_error': p.last_error,
            'last_checked_at': p.last_checked_at, 'accounts': accounts})
    routes = [{'id': r.id, 'profile_id': r.profile_id, 'source_id': r.source_id,
               'destination_id': r.destination_id, 'enabled': r.enabled}
              for r in db.query(BankProfileRoute).filter_by(tenant_id=tenant_id)]
    runs = [{'profile_id': r.profile_id, 'date': r.scheduled_date, 'status': r.status}
            for r in db.query(BankProfileRun).filter_by(tenant_id=tenant_id).order_by(BankProfileRun.started_at.desc()).limit(30)]
    return {'profiles': result, 'routes': routes, 'runs': runs}


@router.get('')
def dashboard(tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    return view(db, tenant_id)


@router.post('/initialize')
def initialize(request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    action(request)
    lock(db, tenant_id)
    profiles.seed_legacy(db, tenant_id)
    db.commit()
    return view(db, tenant_id)


class LinkInput(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    profile_id: str | None = None


@router.post('/link')
def link(data: LinkInput, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    action(request)
    if not data.name.strip():
        raise HTTPException(422, 'Enter a banking profile name.')
    lock(db, tenant_id)
    profile = profiles.owned(db, BankProfile, data.profile_id, tenant_id) if data.profile_id else None
    if not profile and db.query(BankProfile).filter_by(tenant_id=tenant_id).count() >= 20:
        raise HTTPException(409, 'The limit is 20 banking profiles.')
    try:
        token = plaid_bank.link_token(tenant_id, access_token=plaid_bank.decrypt_token(profile.encrypted_access_token) if profile else None, optional_liabilities=True)
    except plaid_bank.PlaidBankError as exc:
        raise HTTPException(503, str(exc)) from None
    attempt = BankProfileLink(id=str(uuid4()), tenant_id=tenant_id, name=data.name.strip(),
        profile_id=profile.id if profile else None, token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    db.add(attempt)
    db.commit()
    return {'link_token': token, 'attempt_id': attempt.id}


class ExchangeInput(StrictModel):
    attempt_id: str
    link_token: str
    public_token: str | None = None


@router.post('/exchange')
def exchange(data: ExchangeInput, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    action(request)
    attempt = db.query(BankProfileLink).filter_by(id=data.attempt_id, tenant_id=tenant_id).with_for_update().first()
    now = datetime.now(timezone.utc)
    if not attempt or attempt.consumed_at or profiles.utc(attempt.expires_at) < now or attempt.token_hash != hashlib.sha256(data.link_token.encode()).hexdigest():
        raise HTTPException(409, 'Bank connection session expired. Start again.')
    attempt.consumed_at = now
    db.commit()
    lock(db, tenant_id)
    if attempt.profile_id:
        profile = profiles.owned(db, BankProfile, attempt.profile_id, tenant_id)
        sync(db, profile)
    else:
        if not data.public_token:
            raise HTTPException(422, 'Plaid did not return a connection token.')
        try:
            token, item_id = plaid_bank.exchange(data.public_token)
            item = plaid_bank.item(token)
            if item.get('item_id') != item_id or not isinstance(item.get('institution_id'), str):
                raise plaid_bank.PlaidBankError('provider_institution_mismatch')
            if db.query(BankProfile).filter_by(item_id=item_id).first():
                raise HTTPException(409, 'This connection already exists. Renew its access instead.')
            profile = BankProfile(id=str(uuid4()), tenant_id=tenant_id, name=attempt.name,
                item_id=item_id, institution_id=item['institution_id'],
                encrypted_access_token=plaid_bank.encrypt_token(token), created_at=now, legacy=False, status='linked')
            db.add(profile)
            db.flush()
            # Save consent even if the first data refresh is temporarily unavailable.
            db.commit()
            sync(db, profile)
        except plaid_bank.PlaidBankError as exc:
            raise HTTPException(422, str(exc)) from None
    db.commit()
    return view(db, tenant_id)


@router.post('/{profile_id}/sync')
def refresh(profile_id: str, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    action(request)
    lock(db, tenant_id)
    profile = profiles.owned(db, BankProfile, profile_id, tenant_id)
    sync(db, profile)
    db.commit()
    return view(db, tenant_id)


class ResolveInput(StrictModel):
    account_id: str | None = None
    separate_account: bool = False


@router.post('/{profile_id}/accounts/{membership_id}/resolve')
def resolve(profile_id: str, membership_id: str, data: ResolveInput, request: Request,
            tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    action(request)
    lock(db, tenant_id)
    profile = profiles.owned(db, BankProfile, profile_id, tenant_id)
    membership = db.query(BankProfileAccount).filter_by(id=membership_id, profile_id=profile.id, active=True).first()
    if not membership or membership.account_id:
        raise HTTPException(409, 'This account is already identified or unavailable.')
    if bool(data.account_id) == data.separate_account:
        raise HTTPException(422, 'Select the same existing account or confirm a separate account.')
    if data.account_id:
        account = profiles.owned(db, BankAccountIdentity, data.account_id, tenant_id)
        if (account.institution_id, account.last4, account.kind) != (profile.institution_id, membership.last4, membership.kind):
            raise HTTPException(422, 'Account identity does not match this connection.')
        if db.query(BankProfileAccount).filter_by(profile_id=profile.id, account_id=account.id, active=True).first():
            raise HTTPException(409, 'Two accounts within one profile cannot be combined.')
    else:
        account = BankAccountIdentity(id=str(uuid4()), tenant_id=tenant_id, institution_id=profile.institution_id,
            last4=membership.last4, kind=membership.kind, name=membership.name, reserve_cents=0)
        db.add(account)
    membership.account_id = account.id
    db.commit()
    return view(db, tenant_id)


class ReserveInput(StrictModel):
    reserve_cents: int = Field(ge=0, le=100000000, strict=True)


@router.put('/accounts/{account_id}/reserve')
def reserve(account_id: str, data: ReserveInput, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    action(request)
    lock(db, tenant_id)
    account = profiles.owned(db, BankAccountIdentity, account_id, tenant_id)
    account.reserve_cents = data.reserve_cents
    db.commit()
    return view(db, tenant_id)


class RouteInput(StrictModel):
    profile_id: str
    source_id: str
    destination_id: str
    bank_route_confirmed: bool


@router.post('/routes')
def route(data: RouteInput, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    action(request)
    lock(db, tenant_id)
    if not data.bank_route_confirmed:
        raise HTTPException(422, 'Confirm this route is available under the selected bank login.')
    row = BankProfileRoute(id=str(uuid4()), tenant_id=tenant_id, profile_id=data.profile_id,
        source_id=data.source_id, destination_id=data.destination_id, enabled=True)
    profiles.route_accounts(db, row)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'This transfer route already exists.') from None
    return view(db, tenant_id)


class RouteState(StrictModel):
    enabled: bool


@router.put('/routes/{route_id}')
def route_state(route_id: str, data: RouteState, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    action(request)
    lock(db, tenant_id)
    row = profiles.owned(db, BankProfileRoute, route_id, tenant_id)
    row.enabled = data.enabled
    db.commit()
    return view(db, tenant_id)


@router.post('/routes/{route_id}/review')
def review(route_id: str, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    action(request)
    lock(db, tenant_id)
    row = profiles.owned(db, BankProfileRoute, route_id, tenant_id)
    profile, _, _ = profiles.route_accounts(db, row)
    sync(db, profile)
    result = profiles.transfer_limit(db, row)
    result.update({'source': 'profile_route', 'route_id': row.id, 'item_id': profile.item_id})
    now = datetime.now(timezone.utc)
    run = BankRepaymentRun(tenant_id=tenant_id, started_at=now, finished_at=now, status='review_required', result=result)
    db.add(run)
    db.commit()
    return {'id': run.id, **result}


class AmountInput(StrictModel):
    amount_cents: int = Field(gt=0, le=100000000, strict=True)


@router.post('/reviews/{review_id}/draft')
def create_draft(review_id: int, data: AmountInput, request: Request, tenant_id: int = Depends(bank_tenant), db: Session = Depends(get_db)):
    action(request)
    lock(db, tenant_id)
    run = db.query(BankRepaymentRun).filter_by(id=review_id, tenant_id=tenant_id).with_for_update().first()
    now = datetime.now(timezone.utc)
    if not run or run.result.get('source') != 'profile_route' or run.result.get('drafts_created') or (now - profiles.utc(run.started_at)).total_seconds() > 300:
        raise HTTPException(409, 'Review expired or already used. Refresh the transfer review.')
    row = profiles.owned(db, BankProfileRoute, run.result['route_id'], tenant_id)
    result = profiles.transfer_limit(db, row)
    if data.amount_cents > min(result['limit_cents'], run.result['limit_cents']):
        raise HTTPException(409, 'Amount exceeds the current available allocation. Refresh the review.')
    draft_id = str(uuid4())
    prefix = 'Rpy' if result['kind'] == 'repayment' else 'Cvr'
    draft = BankTransferDraft(id=draft_id, tenant_id=tenant_id, charge_reference=f'bank-profile-{draft_id}',
        amount_cents=data.amount_cents, from_last4=result['from_last4'], to_last4=result['to_last4'],
        memo=f'{prefix} ELIS {draft_id[:13]}', status='reviewed', created_at=now)
    db.add(draft)
    db.add(BankProfileDraft(draft_id=draft_id, tenant_id=tenant_id, profile_id=row.profile_id,
        route_id=row.id, source_id=row.source_id, destination_id=row.destination_id))
    run.result = {**run.result, 'drafts_created': True, 'draft_ids': [draft_id]}
    db.commit()
    return {'draft': draft_json(draft), 'transfers_executed': False}
