"""Coverage calculation and unapproved scheduled drafts; bank submission is always manual."""
from fastapi import HTTPException
from app.models.bank_monitor import BankAccountIdentity, BankProfileAccount, BankProfileRoute, BankProfileDraft, BankTransferDraft


def proposals(db, profile, *, allow_stale=False, exclude_draft=None):
    from app.services.bank_profile_preferences import preferences
    from app.services.bank_profiles import transfer_limit, utc
    prefs = preferences(db, profile)
    if not prefs['monitor']:
        return []
    members = {a.account_id: a for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True) if a.account_id}
    routes = {r.id: r for r in db.query(BankProfileRoute).filter_by(profile_id=profile.id, tenant_id=profile.tenant_id, enabled=True)}
    incoming = {}
    for draft in db.query(BankTransferDraft).filter_by(tenant_id=profile.tenant_id).filter(BankTransferDraft.status.notin_(['cancelled', 'bank_history_matched'])):
        if draft.id == exclude_draft:
            continue
        binding = db.get(BankProfileDraft, draft.id)
        for key, member in members.items():
            if (binding.destination_id == key if binding else draft.to_last4 == member.last4):
                incoming[key] = incoming.get(key, 0) + draft.amount_cents
    source_allocated = {}
    result = []
    for key, account in sorted(members.items()):
        if account.kind != 'checking':
            continue
        b = account.balance
        current, available, pending = [b.get(k) for k in ('current_cents', 'available_cents', 'pending_debit_cents')]
        reserve = db.get(BankAccountIdentity, key).reserve_cents
        if current is None or available is None or b.get('currency') != 'USD':
            result.append({'account_id': key, 'last4': account.last4, 'name': account.name, 'status': 'balance_unavailable', 'routes': []})
            continue
        minimum = max(0, reserve - min(current, available) - incoming.get(key, 0))
        possible = max(minimum, reserve - min(current, available, current - (pending or 0)) - incoming.get(key, 0))
        if not possible and pending is not None:
            continue
        remaining = possible
        choices = []
        for route_id in prefs['funding_order']:
            route = routes.get(route_id)
            if not route or route.destination_id != key:
                continue
            try:
                cap = transfer_limit(db, route, exclude_draft=exclude_draft, allow_stale=allow_stale)['limit_cents']
                cap = max(0, cap - source_allocated.get(route.source_id, 0))
                amount = min(remaining, cap)
                if amount:
                    source = members[route.source_id]
                    choices.append({'route_id': route.id, 'source_name': source.name, 'source_last4': source.last4,
                                    'amount_cents': amount, 'limit_cents': cap})
                    remaining -= amount
                    source_allocated[route.source_id] = source_allocated.get(route.source_id, 0) + amount
            except (HTTPException, KeyError):
                continue
        ambiguous = possible != minimum or pending is None
        result.append({'account_id': key, 'last4': account.last4, 'name': account.name,
            'status': 'review_required' if choices else 'funding_unavailable',
            'minimum_cents': minimum, 'possible_cents': possible, 'pending_debit_cents': pending,
            'pending_review_required': ambiguous, 'reserve_cents': reserve,
            'incoming_draft_cents': incoming.get(key, 0), 'uncovered_cents': remaining,
            'observed_at': utc(profile.last_checked_at).isoformat() if profile.last_checked_at else None,
            'routes': choices})
    return result


def scheduled_drafts(db, profile):
    """Persist unapproved allocations under the same tenant lock as manual drafts."""
    from datetime import datetime, timezone
    from uuid import uuid4
    from app.models.bank_monitor import BankMonitorConfig
    db.query(BankMonitorConfig).filter_by(tenant_id=profile.tenant_id).with_for_update().one()
    coverage = proposals(db, profile)
    created = []
    for item in coverage:
        for option in item['routes']:
            route = db.get(BankProfileRoute, option['route_id'])
            existing = db.query(BankTransferDraft).join(BankProfileDraft, BankProfileDraft.draft_id == BankTransferDraft.id).filter(
                BankTransferDraft.tenant_id == profile.tenant_id,
                BankProfileDraft.source_id == route.source_id, BankProfileDraft.destination_id == route.destination_id,
                BankTransferDraft.status.notin_(['cancelled', 'bank_history_matched'])).first()
            if existing:
                continue
            id = str(uuid4())
            db.add(BankTransferDraft(id=id, tenant_id=profile.tenant_id, charge_reference=f'bank-profile-scheduled-{id}',
                amount_cents=option['amount_cents'], from_last4=option['source_last4'], to_last4=item['last4'],
                memo=f'Cvr ELIS {id[:13]}', created_at=datetime.now(timezone.utc),
                status='amount_review_required' if item['pending_review_required'] else 'review_required'))
            db.add(BankProfileDraft(draft_id=id, tenant_id=profile.tenant_id, profile_id=profile.id,
                route_id=route.id, source_id=route.source_id, destination_id=route.destination_id))
            created.append(id)
    db.flush()
    return coverage, created
