"""Whole-charge funding. Provider identity, never equal amounts, establishes continuity."""
from datetime import date, datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.models.bank_monitor import (BankFundingCharge, BankFundingFeed, BankProfileAccount,
    BankProfileRoute, BankProfileDraft, BankTransferDraft)

UNAPPROVED = {'review_required', 'amount_review_required'}


def ingest(db, profile, member, entries):
    feed = db.get(BankFundingFeed, member.account_id)
    initial = feed is None
    if initial:
        feed = BankFundingFeed(account_id=member.account_id, tenant_id=profile.tenant_id,
            profile_id=profile.id, initialized_at=datetime.now(timezone.utc), observed_at=datetime.now(timezone.utc))
        db.add(feed)
    # Shared logins must not turn the same bank debit into two charge identities.
    if feed.profile_id != profile.id:
        return
    feed.observed_at = datetime.now(timezone.utc)
    charges = db.query(BankFundingCharge).filter_by(tenant_id=profile.tenant_id, account_id=member.account_id).all()
    seen = set()
    for entry in entries:
        txid = entry.get('transaction_id')
        if not txid or entry.get('currency') != 'USD' or entry.get('amount_cents', 0) <= 0:
            continue
        if entry.get('category') in {'TRANSFER_IN', 'TRANSFER_OUT', 'LOAN_PAYMENTS'}:
            continue  # Do not borrow to fund another transfer or repayment.
        try:
            day = date.fromisoformat(entry['date'])
        except (ValueError, KeyError, TypeError):
            continue
        ids = {v for v in (txid, entry.get('pending_transaction_id')) if v}
        charge = next((c for c in charges if ids.intersection(c.provider_ids)), None)
        if charge is None:
            # Do not backfill old posted expenses when transaction tracking is first enabled.
            historical = not entry.get('pending') and (initial or day < (feed.initialized_at.replace(tzinfo=timezone.utc) if feed.initialized_at.tzinfo is None else feed.initialized_at).astimezone(ZoneInfo('America/New_York')).date())
            duplicate = any(c.origin == 'manual' and c.amount_cents == entry['amount_cents'] and abs((c.charge_date - day).days) <= 7 for c in charges)
            charge = BankFundingCharge(id=str(uuid4()), tenant_id=profile.tenant_id, account_id=member.account_id,
                reference=f'plaid:{txid}', provider_ids=list(ids), description=entry['description'],
                amount_cents=entry['amount_cents'], charge_date=day, pending=entry.get('pending', False), origin='plaid',
                status='duplicate_review' if duplicate else 'historical' if historical else 'eligible', created_at=datetime.now(timezone.utc))
            db.add(charge); charges.append(charge)
        else:
            charge.provider_ids = sorted(set(charge.provider_ids) | ids)
            if charge.amount_cents != entry['amount_cents']:
                draft = db.get(BankTransferDraft, charge.draft_id) if charge.draft_id else None
                if draft and draft.status in UNAPPROVED | {'reviewed'}:
                    draft.amount_cents = entry['amount_cents']
                    draft.status = 'review_required'
            charge.amount_cents = entry['amount_cents']
            charge.description = entry['description']
            charge.pending = entry.get('pending', False)
            charge.charge_date = day
            if charge.status in {'removed', 'removed_historical'}:
                charge.status = 'historical' if charge.status == 'removed_historical' else 'eligible'
        seen.add(charge.id)
    for charge in charges:
        if charge.origin == 'plaid' and charge.id not in seen and charge.status in {'eligible', 'historical'}:
            charge.status = 'removed_historical' if charge.status == 'historical' else 'removed'
    db.flush()


def charge_json(db, charge):
    draft = db.get(BankTransferDraft, charge.draft_id) if charge.draft_id else None
    return {'id': charge.id, 'description': charge.description, 'amount_cents': charge.amount_cents,
        'date': charge.charge_date.isoformat(), 'pending': charge.pending, 'origin': charge.origin,
        'status': ('covered' if draft.amount_cents == charge.amount_cents else 'amount_changed_after_funding') if draft and draft.status == 'bank_history_matched' else
            'dismissed' if draft and draft.status == 'cancelled' else 'drafted' if draft else charge.status,
        'draft_id': charge.draft_id}


def validate_charge(db, draft):
    charge = db.query(BankFundingCharge).filter_by(tenant_id=draft.tenant_id, draft_id=draft.id).first()
    if not charge:
        return None
    if charge.origin == 'plaid':
        from app.services.bank_profiles import utc
        feed = db.get(BankFundingFeed, charge.account_id)
        if not feed or (datetime.now(timezone.utc) - utc(feed.observed_at)).total_seconds() > 300:
            raise HTTPException(409, 'Refresh the bank connection that reports this charge before approving it.')
    if charge.status != 'eligible' or charge.amount_cents != draft.amount_cents:
        raise HTTPException(409, 'This charge changed or is no longer in the bank feed. Review the charge before preparing a transfer.')
    return charge


def proposals(db, profile, *, allow_stale=False, exclude_draft=None):
    from app.services.bank_profile_preferences import preferences
    from app.services.bank_profiles import transfer_limit, utc
    prefs = preferences(db, profile)
    if not prefs['monitor']:
        return []
    members = {a.account_id:a for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True) if a.account_id}
    routes = {r.id:r for r in db.query(BankProfileRoute).filter_by(tenant_id=profile.tenant_id, profile_id=profile.id, enabled=True)}
    allocated = {}
    result = []
    charges = db.query(BankFundingCharge).filter_by(tenant_id=profile.tenant_id, status='eligible').order_by(BankFundingCharge.charge_date, BankFundingCharge.id).all()
    for charge in charges:
        target = members.get(charge.account_id)
        if not target or (charge.draft_id and charge.draft_id != exclude_draft):
            continue
        # An older balance-based draft has no charge attribution. Do not add new funding on top of it.
        unresolved = db.query(BankTransferDraft).join(BankProfileDraft, BankProfileDraft.draft_id == BankTransferDraft.id).filter(
            BankTransferDraft.tenant_id == profile.tenant_id, BankProfileDraft.destination_id == charge.account_id,
            BankTransferDraft.status.notin_(['cancelled', 'bank_history_matched']),
            ~BankTransferDraft.charge_reference.like('bank-profile-charge-%')).first()
        if unresolved:
            continue
        choices = []
        feed = db.get(BankFundingFeed, charge.account_id) if charge.origin == 'plaid' else None
        if charge.origin == 'plaid' and (not feed or (not allow_stale and (datetime.now(timezone.utc) - utc(feed.observed_at)).total_seconds() > 300)):
            continue
        for route_id in prefs['funding_order']:
            route = routes.get(route_id)
            if not route or route.destination_id != charge.account_id:
                continue
            try:
                cap = transfer_limit(db, route, exclude_draft=exclude_draft, allow_stale=allow_stale)['limit_cents'] - allocated.get(route.source_id, 0)
                if cap < charge.amount_cents:
                    continue  # A charge is never split to drain an insufficient credit line.
                source = members[route.source_id]
                choices = [{'route_id':route.id, 'source_name':source.name, 'source_last4':source.last4,
                    'amount_cents':charge.amount_cents, 'limit_cents':cap}]
                allocated[route.source_id] = allocated.get(route.source_id, 0) + charge.amount_cents
                break
            except (HTTPException, KeyError):
                continue
        result.append({'account_id':charge.account_id, 'last4':target.last4, 'name':target.name,
            'charge':charge_json(db, charge), 'status':'review_required' if choices else 'funding_unavailable',
            'minimum_cents':charge.amount_cents, 'possible_cents':charge.amount_cents, 'pending_review_required':False,
            'uncovered_cents':0 if choices else charge.amount_cents, 'routes':choices,
            'observed_at':utc(profile.last_checked_at).isoformat() if profile.last_checked_at else None})
    return result


def make_draft(db, profile, route, charge):
    now = datetime.now(timezone.utc)
    source = db.query(BankProfileAccount).filter_by(profile_id=profile.id, account_id=route.source_id, active=True).one()
    target = db.query(BankProfileAccount).filter_by(profile_id=profile.id, account_id=route.destination_id, active=True).one()
    id = str(uuid4())
    draft = BankTransferDraft(id=id, tenant_id=profile.tenant_id, charge_reference=f'bank-profile-charge-{charge.id}-{id}',
        amount_cents=charge.amount_cents, from_last4=source.last4, to_last4=target.last4,
        memo=f'Cvr ELIS {id[:13]}', status='review_required', created_at=now)
    db.add(draft)
    db.add(BankProfileDraft(draft_id=id, tenant_id=profile.tenant_id, profile_id=profile.id,
        route_id=route.id, source_id=route.source_id, destination_id=route.destination_id))
    charge.draft_id = id
    db.flush()
    return draft


def scheduled_drafts(db, profile):
    from app.models.bank_monitor import BankMonitorConfig
    db.query(BankMonitorConfig).filter_by(tenant_id=profile.tenant_id).with_for_update().one()
    from app.services.bank_profiles import utc, sync_profile, owned
    from app.models.bank_monitor import BankProfile
    accounts = {a.account_id for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True) if a.account_id}
    readers = {f.profile_id for f in db.query(BankFundingFeed).filter_by(tenant_id=profile.tenant_id)
        if f.account_id in accounts and f.profile_id != profile.id and (datetime.now(timezone.utc) - utc(f.observed_at)).total_seconds() > 300}
    for reader in sorted(readers):
        sync_profile(db, owned(db, BankProfile, reader, profile.tenant_id))
    coverage = proposals(db, profile)
    ids = []
    for item in coverage:
        if item['routes']:
            route = db.get(BankProfileRoute, item['routes'][0]['route_id'])
            charge = db.get(BankFundingCharge, item['charge']['id'])
            ids.append(make_draft(db, profile, route, charge).id)
    return coverage, ids


def refresh_charge_feed(db, charge, current_profile):
    from app.models.bank_monitor import BankProfile
    from app.services.bank_profiles import sync_profile, owned
    feed = db.get(BankFundingFeed, charge.account_id) if charge and charge.origin == 'plaid' else None
    if feed and feed.profile_id != current_profile.id:
        sync_profile(db, owned(db, BankProfile, feed.profile_id, current_profile.tenant_id))
