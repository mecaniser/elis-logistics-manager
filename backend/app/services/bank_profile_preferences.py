"""Resolve old suffix-based priorities only through explicitly permitted routes."""
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.models.bank_monitor import BankProfilePreferences, BankProfileRoute, BankProfileAccount, BankMonitorConfig


def preferences(db, profile):
    saved = db.get(BankProfilePreferences, profile.id)
    if saved and saved.settings.get('confirmed'):
        result = {**saved.settings, 'last_evaluation': saved.last_evaluation}
        enabled = {r.id for r in db.query(BankProfileRoute).filter_by(profile_id=profile.id, tenant_id=profile.tenant_id, enabled=True)}
        result['review_required'] = [f'A saved {kind} route is unavailable. Review its priority.' for kind in ('funding', 'repayment') if any(r not in enabled for r in result[f'{kind}_order'])]
        return result
    config = db.get(BankMonitorConfig, profile.tenant_id)
    rules = config.rules if config else {}
    routes = db.query(BankProfileRoute).filter_by(profile_id=profile.id, tenant_id=profile.tenant_id, enabled=True).all()
    members = {a.account_id: a for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True) if a.account_id}
    result = {'monitor': True, 'repayment': bool(rules.get('repayment', {}).get('enabled')), 'funding_order': [], 'repayment_order': [], 'review_required': [], 'last_evaluation': {}}
    # Only the original connection inherits old priorities. Other credentials never
    # acquire old transfer permissions through matching suffixes.
    if not profile.legacy:
        result['repayment'] = False
        return result
    if rules.get('buffer_cents') or rules.get('repayment', {}).get('reserve_cents'):
        result['review_required'].append('Review the account reserves above before replacing the old global buffer and repayment reserve.')
    result['review_required'].append('Connected accounts will replace the old account list. Scheduled checks report balances and route ceilings; automatic proposals require complete bank evidence.')
    for kind, masks in [('funding', [a['last4'] for a in rules.get('sources', [])]), ('repayment', rules.get('repayment', {}).get('priority', []))]:
        for mask in masks:
            candidates = [a for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True, last4=mask)]
            if len(candidates) != 1 or not candidates[0].account_id:
                result['review_required'].append(f'{kind.capitalize()} priority ••{mask} is ambiguous or not linked.')
                continue
            matches = [r for r in routes if r.source_id in members and r.destination_id in members
                       and members[r.source_id if kind == 'funding' else r.destination_id].last4 == mask
                       and members[r.source_id if kind == 'funding' else r.destination_id].kind == 'credit'
                       and members[r.destination_id if kind == 'funding' else r.source_id].kind == 'checking']
            if not matches:
                result['review_required'].append(f'{kind.capitalize()} priority ••{mask} has no permitted route in this login.')
            else:
                result[f'{kind}_order'].extend(r.id for r in sorted(matches, key=lambda r: r.id))
    return result


def evaluate(db, profile, now):
    from app.services.bank_profiles import transfer_limit
    prefs = preferences(db, profile)
    routes = {r.id: r for r in db.query(BankProfileRoute).filter_by(profile_id=profile.id, tenant_id=profile.tenant_id, enabled=True)}
    items = []
    for kind in ('funding', 'repayment'):
        if kind == 'repayment' and (not prefs['repayment'] or now.astimezone(ZoneInfo('America/New_York')).weekday() != 4):
            continue
        for route_id in prefs[f'{kind}_order']:
            route = routes.get(route_id)
            if not route:
                items.append({'route_id': route_id, 'status': 'route_unavailable'})
                continue
            try:
                limit = transfer_limit(db, route)
                items.append({'route_id': route_id, 'kind': kind, 'status': 'evidence_required', 'limit_cents': limit['limit_cents']})
            except HTTPException:
                items.append({'route_id': route_id, 'kind': kind, 'status': 'review_required'})
    # Plaid's pending feed cannot prove completeness or a full payoff. A ceiling
    # is never promoted into a scheduled draft or an instruction to move money.
    return {'observed_at': now.isoformat(), 'status': 'settings_review_required' if prefs['review_required'] else 'evidence_required' if items else 'balances_checked', 'routes': items, 'transfers_executed': False}


def unified(db, tenant_id):
    from app.models.bank_monitor import BankProfile
    profiles = db.query(BankProfile).filter_by(tenant_id=tenant_id).all()
    legacy = [p for p in profiles if p.legacy]
    # Adding another login must never reactivate archived suffix-based rules.
    confirmed = lambda p: bool((row := db.get(BankProfilePreferences, p.id)) and row.settings.get('confirmed', False))
    return all(confirmed(p) for p in legacy) if legacy else any(confirmed(p) for p in profiles)
