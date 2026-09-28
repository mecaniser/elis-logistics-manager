"""Resolve old suffix-based priorities only through explicitly permitted routes."""
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.models.bank_monitor import BankProfilePreferences, BankProfileRoute, BankProfileAccount, BankMonitorConfig


def preferences(db, profile):
    saved = db.get(BankProfilePreferences, profile.id)
    if saved and saved.settings.get('confirmed'):
        result = {**saved.settings, 'funding_order': list(saved.settings['funding_order']), 'repayment_order': list(saved.settings['repayment_order']), 'last_evaluation': saved.last_evaluation}
        enabled = {r.id for r in db.query(BankProfileRoute).filter_by(profile_id=profile.id, tenant_id=profile.tenant_id, enabled=True)}
        all_routes = {r.id: r for r in db.query(BankProfileRoute).filter_by(profile_id=profile.id, tenant_id=profile.tenant_id)}
        members = {a.account_id: a for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True) if a.account_id}
        result['review_items'] = []
        for kind in ('funding', 'repayment'):
            for route_id in result[f'{kind}_order']:
                if route_id in enabled:
                    continue
                route = all_routes.get(route_id)
                source = members.get(route.source_id) if route else None
                target = members.get(route.destination_id) if route else None
                label = f'{source.name} ••{source.last4} → {target.name} ••{target.last4}' if source and target else 'An account transfer that is no longer connected'
                result['review_items'].append({'id': f'{kind}:{route_id}', 'kind': kind, 'route_id': route_id, 'last4': None, 'label': label, 'message': 'This transfer is in your saved plan, but it is turned off or no longer available.'})
        for item in saved.settings.get('pending_review', []):
            kind = item['kind']
            candidates = [a for a in members.values() if a.last4 == item['last4'] and a.kind == 'credit']
            matches = [r.id for r in all_routes.values() if r.enabled and len(candidates) == 1
                       and (r.source_id if kind == 'funding' else r.destination_id) == candidates[0].account_id
                       and members.get(r.destination_id if kind == 'funding' else r.source_id)
                       and members[r.destination_id if kind == 'funding' else r.source_id].kind == 'checking']
            if matches:
                result[f'{kind}_order'].extend(r for r in sorted(matches) if r not in result[f'{kind}_order'])
            else:
                result['review_items'].append(item)
        result['review_required'] = [item['message'] for item in result['review_items']]
        result['migration_pending'] = False
        return result
    config = db.get(BankMonitorConfig, profile.tenant_id)
    rules = config.rules if config else {}
    routes = db.query(BankProfileRoute).filter_by(profile_id=profile.id, tenant_id=profile.tenant_id, enabled=True).all()
    members = {a.account_id: a for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True) if a.account_id}
    result = {'monitor': True, 'repayment': bool(rules.get('repayment', {}).get('enabled')), 'funding_order': [], 'repayment_order': [], 'review_required': [], 'last_evaluation': {}, 'review_items': [], 'migration_pending': bool(profile.legacy)}
    # Only the original connection inherits old priorities. Other credentials never
    # acquire old transfer permissions through matching suffixes.
    if not profile.legacy:
        result['repayment'] = False
        return result
    if rules.get('buffer_cents') or rules.get('repayment', {}).get('reserve_cents'):
        result['review_required'].append('Saving will use the cash reserves shown beside each checking account instead of the previous shared reserve.')
    result['review_required'].append('Saving will use the accounts and cash reserves shown above for future checks.')
    for kind, masks in [('funding', [a['last4'] for a in rules.get('sources', [])]), ('repayment', rules.get('repayment', {}).get('priority', []))]:
        for mask in masks:
            candidates = [a for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id, active=True, last4=mask)]
            if len(candidates) != 1 or not candidates[0].account_id:
                result['review_items'].append({'id': f'{kind}:{mask}', 'kind': kind, 'route_id': None, 'last4': mask, 'label': f'Account ••{mask}', 'message': 'This account cannot be identified in this connection. Connect or identify it above, or remove it from the plan.'})
                result['review_required'].append(f'Account ••{mask} needs attention.')
                continue
            matches = [r for r in routes if r.source_id in members and r.destination_id in members
                       and members[r.source_id if kind == 'funding' else r.destination_id].last4 == mask
                       and members[r.source_id if kind == 'funding' else r.destination_id].kind == 'credit'
                       and members[r.destination_id if kind == 'funding' else r.source_id].kind == 'checking']
            if not matches:
                result['review_items'].append({'id': f'{kind}:{mask}', 'kind': kind, 'route_id': None, 'last4': mask, 'label': f'{candidates[0].name} ••{mask}', 'message': 'Previously selected to fund checking, but no transfer into checking is enabled.' if kind == 'funding' else 'Previously selected for payments, but no payment from checking is enabled.'})
                result['review_required'].append(f'Account ••{mask} needs an enabled transfer or removal from the plan.')
            else:
                result[f'{kind}_order'].extend(r.id for r in sorted(matches, key=lambda r: r.id))
    return result


def evaluate(db, profile, now, *, create_drafts=False):
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
    from app.services.bank_charge_funding import proposals
    coverage = proposals(db, profile)
    draft_ids = []
    if create_drafts:
        from app.services.bank_charge_funding import scheduled_drafts
        coverage, draft_ids = scheduled_drafts(db, profile)
    summary = (f'{len(draft_ids)} coverage draft(s) created for your review.' if draft_ids else
        'No new draft: review account data, funding routes, or existing drafts.' if coverage else
        'No new uncovered charges found. Existing drafts and previously covered charges are excluded.')
    return {'summary': summary, 'draft_ids': draft_ids, 'coverage': coverage, 'observed_at': now.isoformat(), 'status': 'coverage_review_required' if coverage else 'settings_review_required' if prefs['review_required'] else 'evidence_required' if items else 'balances_checked', 'routes': items, 'transfers_executed': False}


def unified(db, tenant_id):
    from app.models.bank_monitor import BankProfile
    profiles = db.query(BankProfile).filter_by(tenant_id=tenant_id).all()
    legacy = [p for p in profiles if p.legacy]
    # Adding another login must never reactivate archived suffix-based rules.
    confirmed = lambda p: bool((row := db.get(BankProfilePreferences, p.id)) and row.settings.get('confirmed', False))
    return all(confirmed(p) for p in legacy) if legacy else any(confirmed(p) for p in profiles)
