"""Coverage suggestions only. Ambiguous pending debits require human reconciliation."""
from fastapi import HTTPException
from app.models.bank_monitor import BankAccountIdentity, BankProfileAccount, BankProfileRoute, BankProfileDraft, BankTransferDraft


def proposals(db, profile, *, allow_stale=False):
    from app.services.bank_profile_preferences import preferences
    from app.services.bank_profiles import transfer_limit, utc
    prefs = preferences(db, profile)
    if not prefs['monitor']:
        return []
    members = {a.account_id: a for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True) if a.account_id}
    routes = {r.id: r for r in db.query(BankProfileRoute).filter_by(profile_id=profile.id, tenant_id=profile.tenant_id, enabled=True)}
    incoming = {}
    for draft in db.query(BankTransferDraft).filter_by(tenant_id=profile.tenant_id).filter(BankTransferDraft.status.notin_(['cancelled', 'bank_history_matched'])):
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
                cap = transfer_limit(db, route, allow_stale=allow_stale)['limit_cents']
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
