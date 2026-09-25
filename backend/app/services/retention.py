"""Period management contribution, distinct from bank cash and book net income."""
from collections import defaultdict
from app.models.repair import Repair
from app.models.truck import Truck
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal
from app.services.finance import ACCOUNTS, D, ZERO, money, state

DEFAULT_TARGETS = {'target_percent': '30.00', 'acceptable_percent': '28.00', 'effective_date': None}


def score(retained, gross, target, floor):
    if gross <= 0:
        return {'retained_per_100': None, 'score': None, 'band': 'no_revenue'}
    percent = retained / gross * 100
    return {'retained_per_100': money(percent), 'score': money(percent / target * 100),
            'band': 'target_met' if percent >= target else ('acceptable' if percent >= floor else 'below_floor')}


def allocate(total, weights):
    """Exact cents; largest remainders, with asset ID as the stable tie breaker."""
    positive = {k: v for k, v in weights.items() if v > 0}
    denominator = sum(positive.values(), ZERO)
    if not denominator:
        return {k: ZERO for k in weights}
    cents = int(abs(total) * 100)
    exact = {k: Decimal(cents) * v / denominator for k, v in positive.items()}
    parts = {k: int(v) for k, v in exact.items()}
    for k in sorted(parts, key=lambda k: (-(exact[k] - parts[k]), k))[:cents - sum(parts.values())]:
        parts[k] += 1
    return {k: Decimal(parts.get(k, 0)) / 100 * (-1 if total < 0 else 1) for k in weights}


def covered(s):
    remaining = {r['id']: max(r['balance'], ZERO) for r in s['reserves'].values()}
    pairs = {r['id']: r['pair_id'] for r in s['reserves'].values()}
    result = defaultdict(lambda: ZERO)
    for claim in s['claims'].values():
        rid = claim.get('reserve_id')
        amount = min(max(claim['remaining'], ZERO), remaining.get(rid, ZERO))
        if rid in pairs:
            remaining[rid] -= amount
            result[pairs[rid]] += amount
    return result


def retention_report(db, tenant, report):
    start, end = (date.fromisoformat(report['period'][k]) for k in ('start', 'end'))
    before = state(db, tenant, start - timedelta(days=1)) if start > date.min else state(db, tenant, date.min)
    closing = state(db, tenant, end)
    settings = state(db, tenant, date.max)
    timezone = (settings['policy'] or {}).get('timezone', 'UTC')
    targets = dict(DEFAULT_TARGETS)
    for e in closing['events']:
        if e.kind == 'retention_targets' and e.effective_date <= start:
            targets = {**e.payload, 'effective_date': e.effective_date.isoformat()}
    pairs = report['pairs']
    ids = {p['truck_id'] for p in pairs}
    weights = {p['truck_id']: D(p['freight_gross']) for p in pairs}
    contribution = defaultdict(lambda: ZERO)
    sources = defaultdict(set)
    gaps = defaultdict(list)

    def owner(asset, when, explicit=None):
        if explicit in ids:
            return explicit
        if asset in ids:
            return asset
        matched = {a['truck_id'] for a in closing['assignments'] if a['trailer_id'] == asset and a['start'] <= when <= (a.get('end') or '9999-12-31')}
        return next(iter(matched)) if len(matched) == 1 else None

    event_map = {e.id: e for e in closing['events']}
    shared = unassigned = ZERO
    for line in report['ledger']['general_ledger']:
        # Book depreciation and disposal are ownership results, not current freight retention.
        if line['account'] in ('depreciation', 'disposal_gain') or ACCOUNTS[line['account']] not in ('expense', 'revenue'):
            continue
        event = event_map.get(line['event_id'])
        payload = event.payload if event else {}
        pair = owner(line['asset_id'], line['date'], payload.get('pair_id'))
        value = D(line['credit']) - D(line['debit'])
        if pair is not None:
            contribution[pair] += value
            sources[pair].add(line['event_id'])
        elif line['asset_id'] is None:
            shared += value
        else:
            unassigned += value
    # Management-only bridge: legacy repairs remain expenses even when owner
    # repayment history is not posted. Never duplicate an explicitly linked bill,
    # including a reversed bill that needs an accounting correction.
    linked_repairs = {e.payload.get('legacy_repair_id') for e in closing['events']
                      if e.kind in ('bill', 'owner_advance')}
    historical_repairs = defaultdict(lambda: ZERO)
    historical_ids = defaultdict(list)
    for repair in db.query(Repair).join(Truck, Repair.truck_id == Truck.id).filter(
            Truck.tenant_id == tenant, Repair.repair_date >= start, Repair.repair_date <= min(end, date.fromisoformat(report['as_of']))):
        if repair.id in linked_repairs or repair.cost is None:
            continue
        pair = owner(repair.truck_id, repair.repair_date.isoformat())
        if pair is None:
            unassigned -= D(repair.cost)
            continue
        historical_repairs[pair] += D(repair.cost)
        historical_ids[pair].append(repair.id)
    shares = allocate(shared, weights)
    reserve_delta = defaultdict(lambda: ZERO)
    funding = defaultdict(lambda: ZERO)
    opening_balances = defaultdict(lambda: ZERO)
    closing_balances = defaultdict(lambda: ZERO)
    for r in before['reserves'].values(): opening_balances[r['pair_id']] += r['balance']
    for r in closing['reserves'].values(): closing_balances[r['pair_id']] += r['balance']
    principal = defaultdict(lambda: ZERO)
    for e in closing['events']:
        if not start <= e.effective_date <= end or e.id not in closing['active_event_ids']:
            continue
        p = e.payload
        if e.kind == 'reserve':
            reserve_delta[p['pair_id']] += D(p['amount'])
            if not p.get('opening'):
                funding[p['pair_id']] += max(D(p['amount']), ZERO)
            sources[p['pair_id']].add(e.id)
        elif e.kind == 'payment':
            claim = closing['claims'].get(p['claim_id'], {})
            if claim.get('category') != 'equipment':
                continue  # Interest and operating bills are already incurred in the ledger.
            pair = owner(claim.get('asset_id'), e.effective_date.isoformat(), claim.get('pair_id'))
            if p['payer'] == 'business' and pair is not None:
                principal[pair] += D(p['amount'])
                sources[pair].add(e.id)
            elif p['payer'] == 'card':
                for i in ids: gaps[i].append('Equipment charged to a card needs principal repayment attribution.')
        elif e.kind == 'reversal':
            for i in ids: gaps[i].append('A posting reversal affects this period; review reserve and financing attribution.')
    cover_before, cover_end = covered(before), covered(closing)
    result = []
    for p in pairs:
        i = p['truck_id']
        used = opening_balances[i] + reserve_delta[i] - closing_balances[i]
        repair_offset = used + cover_end[i] - cover_before[i]
        remainder = sum((D(s['reported_payout']) for s in p['settlements']), ZERO)
        rows = [
            ('Statement remainder', remainder),
            ('Outside costs and income, including incurred interest', contribution[i] - remainder),
            ('Historical repairs not yet posted to Accounting', -historical_repairs[i]),
            ('Shared company result allocated by freight', shares[i]),
            ('Business-paid equipment obligations', -principal[i]),
            ('New repair and capital funding', -funding[i]),
            ('Repair costs covered by protected funds', repair_offset),
        ]
        retained = sum((amount for _, amount in rows), ZERO)
        # No per-period completeness attestation exists yet. Never promote a partial
        # evidence calculation to final take-home pay on the strength of a global policy.
        issues = [
            'Outside bills and income must be reconciled for the complete selected period.',
            'Verify repair and capital funding against required targets; unfunded targets are not deducted here.',
            'Verify financing statements and scheduled obligations. This period score is not cash available to withdraw.',
        ] + gaps[i]
        if historical_ids[i]:
            issues.append('Historical repair costs are included from the repair register; payment and reserve treatment must be reconciled before finalized accounting.')
        if not all(a in closing['plans'] for a in p['asset_ids']):
            issues.append('Equipment acquisition, resale and payoff evidence is incomplete.')
        if report['owner_insights']['unposted_in_period']:
            issues.append('Some historical settlements in this period are not yet posted.')
        if unassigned:
            issues.append('Unassigned asset costs or income require a dated equipment assignment.')
        if not p['trailer_ids']:
            issues.append('Trailer assignment is not established.')
        result.append({'asset_id': i, 'retained': money(retained), 'freight': money(weights[i]),
                       **score(retained, weights[i], D(targets['target_percent']), D(targets['acceptable_percent'])),
                       'status': 'provisional', 'issues': list(dict.fromkeys(issues)),
                       'bridge': [{'label': label, 'amount': money(amount)} for label, amount in rows],
                       'source_event_ids': sorted(sources[i]), 'source_repair_ids': sorted(historical_ids[i])})
    return {'version': 1, 'period': report['period'], 'as_of': report['as_of'],
            'basis': 'recorded_period_contribution_after_funded_protection', 'targets': targets,
            'settings_timezone': timezone, 'minimum_effective_date': datetime.now(ZoneInfo(timezone)).date().isoformat(),
            'scheduled_targets': [{**e.payload, 'effective_date': e.effective_date.isoformat()} for e in settings['events'] if e.kind == 'retention_targets' and e.effective_date > start],
            'pairs': result, 'unallocated_company_result': money(shared - sum(shares.values(), ZERO)),
            'unassigned_asset_result': money(unassigned),
            'note': 'Score = retained per $100 ÷ target × 100. No cap; losses remain negative. Shared overhead is allocated for comparison only and remains recorded once in the company ledger. Driver names are current asset labels, not verified historical driver assignments.'}
