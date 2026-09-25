"""Source-aware owner comparisons. No fuel-derived distance or invented savings."""
from collections import defaultdict
from decimal import Decimal
from app.services.finance import D, ZERO, money, EXPENSE_MAP


def ratio(value, denominator, places='0.01'):
    return str((D(value) / D(denominator)).quantize(Decimal(places))) if denominator else None


def owner_insights(report):
    pairs, issues = [], []
    for pair in sorted(report['pairs'], key=lambda p: p['name']):
        statements = pair['settlements']
        categories = defaultdict(lambda: ZERO)
        for source in statements:
            categories['carrier'] += D(source['carrier_retention'])
            for key, value in source['deductions'].items():
                categories[EXPENSE_MAP.get(key, key)] += D(value)
        eligible = [s for s in statements if s.get('miles') and D(s['miles']) > 0 and s.get('mileage_basis') in ('reported', 'independent')]
        miles = sum((D(s['miles']) for s in eligible), ZERO)
        complete = bool(statements) and len(eligible) == len(statements)
        denominator = miles if complete else ZERO
        gross = sum((D(s['freight_gross']) for s in statements), ZERO)
        remainder = sum((D(s['reported_payout']) for s in statements), ZERO)
        loads = [load for s in statements for load in s['loads']]
        empty = sum((D(l['empty_miles']) for l in loads), ZERO)
        loaded = sum((D(l['loaded_miles']) for l in loads), ZERO)
        load_coverage = complete and bool(loads) and empty + loaded == miles
        for s in statements:
            future = [l['load_id'] for l in s['loads'] if l['delivery'] > s['date']]
            if future:
                issues.append({'code': 'service_date', 'asset_id': pair['truck_id'], 'title': f"{pair['name']}: delivery after statement date", 'detail': f"{s['source_ref']} includes load(s) {', '.join(future)} delivered after {s['date']}. Review service dates before finalizing period earnings.", 'href': '/finance/settlements'})
        unknown_fuel = sum(1 for s in statements for fuel in s['fuel'] if fuel['product'] == 'unknown')
        if unknown_fuel:
            issues.append({'code': 'fuel_products', 'asset_id': pair['truck_id'], 'title': f"{pair['name']}: verify fuel products", 'detail': f'{unknown_fuel} purchase rows do not identify diesel versus other products. Fuel charges per mile are a spending comparison, not measured consumption.', 'href': '/finance/connections'})
        pairs.append({
            'asset_id': pair['truck_id'], 'name': pair['name'], 'trailer_ids': pair['trailer_ids'],
            'freight': money(gross), 'remainder': money(remainder), 'recorded_net': pair['earnings'],
            'outside_statement_effect': money(D(pair['earnings']) - remainder),
            'remainder_per_calendar_day': ratio(remainder, report['period']['calendar_days']),
            'miles': money(miles) if complete else None, 'mileage_basis': 'reported' if any(s['mileage_basis'] == 'reported' for s in eligible) else ('independent' if complete else 'incomplete'),
            'covered_statements': len(eligible), 'statement_count': len(statements),
            'freight_per_mile': ratio(gross, denominator, '0.001'), 'fuel_per_mile': ratio(categories['fuel'], denominator, '0.001'),
            'remainder_per_mile': ratio(remainder, denominator, '0.001'), 'empty_mile_percent': ratio(empty * 100, miles) if load_coverage else None,
            'source_start': min((s['period_start'] for s in statements), default=None), 'source_end': max((s['period_end'] for s in statements), default=None),
            'categories': {k: money(v) for k, v in categories.items()},
            'shares': {k: ratio(v * 100, gross) for k, v in categories.items()},
            'remainder_percent': ratio(remainder * 100, gross),
            'source_ids': [s['evidence_id'] for s in statements],
        })
    comparisons = []
    active = [p for p in pairs if p['statement_count']]
    if len(active) == 2:
        base, compared = active
        effects = [{'category': 'freight', 'amount': money(D(compared['freight']) - D(base['freight']))}]
        for category in sorted(set(base['categories']) | set(compared['categories'])):
            effects.append({'category': category, 'amount': money(D(base['categories'].get(category, 0)) - D(compared['categories'].get(category, 0)))})
        effects = sorted((e for e in effects if D(e['amount'])), key=lambda e: abs(D(e['amount'])), reverse=True)
        difference = D(compared['remainder']) - D(base['remainder'])
        assert sum((D(e['amount']) for e in effects), ZERO) == difference
        rate_change = None
        if base['fuel_per_mile'] and compared['fuel_per_mile'] and D(base['categories']['fuel']) > 0:
            rate_change = money(((D(compared['categories']['fuel']) / D(compared['miles'])) / (D(base['categories']['fuel']) / D(base['miles'])) - 1) * 100)
        comparisons.append({'base_id': base['asset_id'], 'compared_id': compared['asset_id'], 'base_name': base['name'], 'compared_name': compared['name'], 'difference': money(difference), 'effects': effects, 'fuel_rate_change_percent': rate_change, 'basis': 'settlement_remainder', 'note': 'Statement groups can cover different service dates. Costs per reported mile are purchase-period comparisons; routes, prices, timing, idling and distance coverage need review.'})
    # One time axis, separate series per power unit; missing dates remain null, never zero.
    timeline = {}
    for pair in report['pairs']:
        for s in pair['settlements']:
            point = timeline.setdefault(s['date'], {'date': s['date']})
            point[str(pair['truck_id'])] = money(D(point.get(str(pair['truck_id']), 0)) + D(s['reported_payout']))
    posted_ids = {s.get('legacy_id') for p in report['pairs'] for s in p['settlements']}
    pending = sum(r['legacy_id'] not in posted_ids for r in report['legacy_comparison']['rows'])
    return {'unposted_in_period': pending, 'basis': 'settlement_statement_date', 'pairs': pairs, 'comparisons': comparisons, 'issues': issues, 'trend': [timeline[d] for d in sorted(timeline)], 'note': 'Settlement results are supported by source statements. Bank receipts, outside bills, asset funding and service-date adjustments require separate reconciliation.'}
