"""Account identity and profile-scoped transfer limits. Never submit bank transfers."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException
from app.models.bank_monitor import (BankProfile, BankProfileAccount, BankAccountIdentity,
    BankProfileRoute, BankProfileDraft, BankProviderConnection, BankMonitorConfig, BankTransferDraft)
from app.services import plaid_bank


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def owned(db, model, identity, tenant_id):
    row = db.query(model).filter_by(id=identity, tenant_id=tenant_id).first()
    if not row:
        raise HTTPException(404, 'Bank profile or account unavailable.')
    return row


def seed_legacy(db, tenant_id):
    """Copy consent, not credentials; old schema and unfinished drafts remain intact."""
    legacy = db.get(BankProviderConnection, tenant_id)
    if not legacy or db.query(BankProfile).filter_by(item_id=legacy.item_id).first():
        return
    config = db.query(BankMonitorConfig).filter_by(tenant_id=tenant_id).with_for_update().first()
    if db.query(BankProfile).filter_by(item_id=legacy.item_id).first():
        return
    profile = BankProfile(id=str(uuid4()), tenant_id=tenant_id, name='Truliant — Consolidated',
        item_id=legacy.item_id, institution_id=legacy.institution_id,
        encrypted_access_token=legacy.encrypted_access_token, legacy=True,
        status='refresh_required', created_at=datetime.now(timezone.utc))
    db.add(profile)
    rules = config.rules if config else {}
    names = {a['last4']: a['nickname'] for a in rules.get('checking', []) + rules.get('sources', [])}
    for mask, mapping in legacy.account_map.items():
        account = BankAccountIdentity(id=str(uuid4()), tenant_id=tenant_id, institution_id=legacy.institution_id,
            name=names.get(mask, f'Account ••{mask}'), last4=mask, kind=mapping['kind'],
            reserve_cents=max(rules.get('buffer_cents') or 0, rules.get('repayment', {}).get('reserve_cents') or 0))
        db.add(account)
        db.add(BankProfileAccount(id=str(uuid4()), profile_id=profile.id, account_id=account.id,
            provider_account_id=mapping['account_id'], name=account.name, last4=mask,
            kind=account.kind, active=True, balance={}))
    db.flush()


def discover(db, profile, rows):
    existing = {a.provider_account_id: a for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id)}
    for account in existing.values():
        account.active = False
    for row in rows:
        kind = 'checking' if row.get('type') == 'depository' and row.get('subtype') == 'checking' else 'credit' if row.get('type') in {'credit', 'loan'} else None
        mask, provider_id = row.get('mask'), row.get('account_id')
        if not kind or not isinstance(mask, str) or len(mask) != 4 or not mask.isdigit() or not isinstance(provider_id, str):
            continue
        membership = existing.get(provider_id)
        if membership and (membership.last4 != mask or membership.kind != kind):
            raise plaid_bank.PlaidBankError('provider_account_identity_changed')
        if not membership:
            name = str(row.get('name') or kind)[:80]
            candidates = db.query(BankAccountIdentity).filter_by(tenant_id=profile.tenant_id,
                institution_id=profile.institution_id, last4=mask, kind=kind).all()
            canonical = None
            # A mask match is a candidate, never proof of shared account identity.
            if not candidates:
                canonical = BankAccountIdentity(id=str(uuid4()), tenant_id=profile.tenant_id,
                    institution_id=profile.institution_id, name=name, last4=mask, kind=kind, reserve_cents=0)
                db.add(canonical)
                db.flush()
            membership = BankProfileAccount(id=str(uuid4()), profile_id=profile.id,
                account_id=canonical.id if canonical else None, provider_account_id=provider_id,
                name=name, last4=mask, kind=kind, balance={})
            db.add(membership)
        membership.name = str(row.get('name') or row.get('official_name') or membership.name)[:80]
        membership.active = True
        membership.subtype = row.get('subtype')
        b = row.get('balances') or {}
        membership.balance = {'current_cents': plaid_bank.cents(b.get('current')),
            'available_cents': plaid_bank.cents(b.get('available')),
            'currency': b.get('iso_currency_code'), 'pending_debit_cents': None}
    db.flush()


def sync_profile(db, profile):
    try:
        token = plaid_bank.decrypt_token(profile.encrypted_access_token)
        item = plaid_bank.item(token)
        if item.get('item_id') != profile.item_id or item.get('institution_id') != profile.institution_id:
            raise plaid_bank.PlaidBankError('provider_institution_mismatch')
        rows = plaid_bank.real_time_accounts(token)
        discover(db, profile, rows)
        memberships = db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True).all()
        if not memberships:
            raise plaid_bank.PlaidBankError('provider_no_supported_accounts')
        mapping = {a.id: {'account_id': a.provider_account_id, 'kind': a.kind} for a in memberships}
        visibility = plaid_bank.transaction_visibility(token, mapping)
        for a in memberships:
            a.balance = {**a.balance, 'pending_debit_cents': visibility['pending_debit_cents'].get(a.id, 0),
                'pending_count': visibility['pending_entries'].get(a.id, 0),
                'transactions_updated_at': visibility.get('last_successful_update')}
        profile.status, profile.last_error = 'synced', None
        profile.last_checked_at = datetime.now(timezone.utc)
    except plaid_bank.PlaidBankError as exc:
        profile.status, profile.last_error = 'read_blocked', str(exc)
        raise


def member(db, profile, account_id):
    rows = db.query(BankProfileAccount).filter_by(profile_id=profile.id, account_id=account_id, active=True).all()
    if len(rows) != 1:
        raise HTTPException(409, 'Resolve account identity in this banking profile first.')
    return rows[0]


def route_accounts(db, route):
    profile = owned(db, BankProfile, route.profile_id, route.tenant_id)
    if profile.institution_id != plaid_bank.TRULIANT_INSTITUTION_ID:
        raise HTTPException(409, 'Form preparation is currently supported only for Truliant. External-bank routes are not enabled.')
    if not route.enabled:
        raise HTTPException(409, 'This transfer route is disabled.')
    source, destination = member(db, profile, route.source_id), member(db, profile, route.destination_id)
    if source.id == destination.id or source.last4 == destination.last4:
        raise HTTPException(409, 'The bank form must identify source and destination unambiguously.')
    all_members = db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True).all()
    if any(sum(a.last4 == suffix for a in all_members) != 1 for suffix in [source.last4, destination.last4]):
        raise HTTPException(409, 'Duplicate account suffixes cannot be used for browser form preparation.')
    if source.kind == 'credit' and (destination.kind != 'checking' or source.subtype not in {'line of credit', 'home equity'}):
        raise HTTPException(409, 'Only a bank-reported credit line can fund checking. Credit-card advances are not supported.')
    return profile, source, destination


def transfer_limit(db, route, exclude_draft=None):
    profile, source, destination = route_accounts(db, route)
    if profile.status != 'synced' or not profile.last_checked_at or (datetime.now(timezone.utc) - utc(profile.last_checked_at)).total_seconds() > 300:
        raise HTTPException(409, 'Refresh this banking profile before reviewing a transfer.')
    balances = source.balance
    if balances.get('currency') != 'USD' or destination.balance.get('currency') != 'USD':
        raise HTTPException(409, 'Only verified US dollar balances are supported.')
    current, available, pending = (balances.get(k) for k in ['current_cents', 'available_cents', 'pending_debit_cents'])
    if available is None or (source.kind == 'checking' and (current is None or pending is None)):
        raise HTTPException(409, 'Source balance or transaction data is unavailable. Refresh bank data.')
    account = owned(db, BankAccountIdentity, source.account_id, profile.tenant_id)
    cap = available if source.kind == 'credit' else min(current, available, current - pending) - account.reserve_cents
    queued, incoming = 0, 0
    for draft in db.query(BankTransferDraft).filter_by(tenant_id=profile.tenant_id).filter(BankTransferDraft.status.notin_(['cancelled', 'bank_history_matched'])):
        if draft.id == exclude_draft:
            continue
        binding = db.get(BankProfileDraft, draft.id)
        # Legacy drafts have no account IDs: reserve conservatively for matching suffixes.
        if (binding.source_id == source.account_id if binding else draft.from_last4 == source.last4):
            queued += draft.amount_cents
        if (binding.destination_id == destination.account_id if binding else draft.to_last4 == destination.last4):
            incoming += draft.amount_cents
    cap -= queued
    if destination.kind == 'credit':
        owed = destination.balance.get('current_cents')
        if owed is None:
            raise HTTPException(409, 'The destination balance owed is unavailable.')
        cap = min(cap, owed - incoming)
    return {'limit_cents': max(0, cap), 'reserved_draft_cents': queued,
        'reserve_cents': account.reserve_cents, 'pending_debit_cents': pending,
        'profile_name': profile.name, 'profile_id': profile.id,
        'from_last4': source.last4, 'to_last4': destination.last4,
        'source_name': source.name, 'destination_name': destination.name,
        'kind': 'repayment' if destination.kind == 'credit' else 'coverage',
        'observed_at': utc(profile.last_checked_at).isoformat(), 'pending_complete': False}


def draft_session(db, draft):
    binding = db.get(BankProfileDraft, draft.id)
    if not binding:
        return None
    profile = owned(db, BankProfile, binding.profile_id, draft.tenant_id)
    source = db.query(BankProfileAccount).filter_by(profile_id=profile.id, account_id=binding.source_id).first()
    destination = db.query(BankProfileAccount).filter_by(profile_id=profile.id, account_id=binding.destination_id).first()
    return {'profile_id': profile.id, 'profile_name': profile.name,
        'source_name': source.name, 'destination_name': destination.name,
        'institution_id': profile.institution_id}


def run_due_profiles(db, now):
    """Independent daily reads: one failed consent does not stop other profiles."""
    import os
    from app.models.bank_monitor import BankProfileRun
    from app.models.tenant import Tenant
    from app.services.bank_monitor import EASTERN
    local = now.astimezone(EASTERN)
    allowed = {int(v.strip()) for v in os.getenv('BANK_MONITOR_TENANT_IDS', '').split(',') if v.strip().isdigit()}
    db.query(BankProfileRun).filter(BankProfileRun.tenant_id.in_(allowed), BankProfileRun.status == 'running', BankProfileRun.started_at < now - timedelta(minutes=10)).update({'status': 'read_interrupted', 'finished_at': now}, synchronize_session=False)
    db.commit()
    if (local.hour, local.minute) < (17, 30):
        return
    rows = db.query(BankProfile).join(BankMonitorConfig, BankMonitorConfig.tenant_id == BankProfile.tenant_id).join(Tenant, Tenant.id == BankProfile.tenant_id).filter(BankProfile.tenant_id.in_(allowed), BankMonitorConfig.enabled.is_(True), Tenant.is_active.is_(True)).all()
    for profile in rows:
        if db.query(BankProfileRun).filter_by(profile_id=profile.id, scheduled_date=local.date()).first():
            continue
        run = BankProfileRun(id=str(uuid4()), tenant_id=profile.tenant_id, profile_id=profile.id,
            scheduled_date=local.date(), started_at=now, status='running')
        db.add(run)
        from sqlalchemy.exc import IntegrityError
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        try:
            sync_profile(db, profile)
            run.status = 'synced'
        except plaid_bank.PlaidBankError as exc:
            run.status = str(exc)
        except Exception:
            db.rollback()
            run = db.get(BankProfileRun, run.id)
            run.status = 'read_failed'
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
