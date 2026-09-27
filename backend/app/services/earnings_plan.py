"""Read-only planning bridge. Saved targets are not reserve balances or payments."""
from datetime import date, timedelta
from decimal import Decimal
from app.models.truck import Truck
from app.services.finance import D, ZERO, money, state


def period_target(weekly, start, end):
    """Cumulative cent rounding makes adjacent calendar periods additive."""
    anchor = date(1970, 1, 1)
    def accrued(day):
        return D(money(D(weekly) * Decimal((day - anchor).days) / 7))
    return accrued(end + timedelta(days=1)) - accrued(start)


def saved_plan(vehicle):
    cost = vehicle.total_cost
    resale = vehicle.expected_resale_value
    weeks = vehicle.planned_service_weeks
    target = max(D(cost) - D(resale), ZERO) if cost is not None and resale is not None else None
    weekly = target / weeks if target is not None and weeks and weeks > 0 else vehicle.trailer_depreciation_reserve_amount
    return {'asset_id': vehicle.id, 'name': vehicle.name, 'vin': vehicle.vin,
            'cash_investment': money(vehicle.cash_investment) if vehicle.cash_investment is not None else None,
            'cost': money(cost) if cost is not None else None,
            'resale': money(resale) if resale is not None else None,
            'service_weeks': weeks, 'capital_target': money(target) if target is not None else None,
            'capital_weekly': money(weekly) if weekly is not None else None,
            'repair_weekly': money(vehicle.default_repair_reserve_amount) if vehicle.default_repair_reserve_amount is not None else None,
            'original_loan': money(vehicle.loan_amount) if vehicle.loan_amount is not None else None,
            'annual_rate': str(vehicle.interest_rate) if vehicle.interest_rate is not None else None,
            'source': f'/vehicles/{vehicle.id}', '_weekly': weekly, '_start': vehicle.purchase_date, '_end': (vehicle.purchase_date + timedelta(weeks=weeks) - timedelta(days=1)) if vehicle.purchase_date and weeks else None}


def earnings_plan(db, tenant, report):
    start = date.fromisoformat(report['period']['start'])
    end = min(date.fromisoformat(report['period']['end']), date.fromisoformat(report['as_of']))
    closing = state(db, tenant, end)
    assets = {v.id: v for v in db.query(Truck).filter_by(tenant_id=tenant).all()}
    saved = {i: saved_plan(v) for i, v in assets.items()}
    for aid, plan in closing['plans'].items():
        if aid in saved:
            target = max(D(plan['acquisition_cost']) - max(D(plan['expected_resale']) - D(plan['selling_costs']), ZERO), ZERO)
            days = (date.fromisoformat(plan['planned_sale']) - date.fromisoformat(plan['acquired'])).days
            saved[aid].update(capital_target=money(target), capital_weekly=money(target * 7 / days) if days > 0 else None, _weekly=target * 7 / days if days > 0 else None, source='/finance/assets', _start=date.fromisoformat(plan['acquired']), _end=date.fromisoformat(plan['planned_sale']) - timedelta(days=1))
    scores = {p['asset_id']: p for p in report['retention']['pairs']}
    pair_rows = []
    for pair in report['pairs']:
        i = pair['truck_id']
        if i not in assets or i not in scores:
            continue
        score = scores[i]
        issues = []
        repair_weekly = assets[i].default_repair_reserve_amount
        if repair_weekly is None:
            issues.append('Weekly repair target is not saved on this vehicle.')
        repair_target = period_target(repair_weekly, start, end) if repair_weekly is not None and end >= start else ZERO
        capital_target = ZERO
        for aid in pair['asset_ids']:
            plan = saved.get(aid)
            if not plan:
                continue
            if plan['_weekly'] is None:
                if D(plan['cost']) > 0 or D(plan['cash_investment']) > 0:
                    issues.append(f"{plan['name']}: acquisition information exists; resale or recovery duration is missing.")
            elif end >= start:
                active_start = max(start, plan['_start'] or start)
                active_end = min(end, plan['_end'] or end)
                if not plan['_start']:
                    issues.append(f"{plan['name']}: saved target is reused; acquisition date is needed to establish its recovery horizon.")
                # A reassigned trailer contributes only on its documented days.
                if aid == i:
                    capital_target += period_target(plan['_weekly'], active_start, active_end) if active_end >= active_start else ZERO
                else:
                    intervals = [(max(active_start, date.fromisoformat(a['start'])), min(active_end, date.fromisoformat(a.get('end') or end.isoformat()))) for a in closing['assignments'] if a['truck_id'] == i and a['trailer_id'] == aid]
                    covered_days = set()
                    for first, last in intervals:
                        while first <= last:
                            covered_days.add(first)
                            first += timedelta(days=1)
                    capital_target += sum((period_target(plan['_weekly'], day, day) for day in covered_days), ZERO)
                    if len(covered_days) < (end - start).days + 1:
                        issues.append(f"{plan['name']}: saved recovery plan exists; dated assignment is needed for period allocation.")
        # The retention bridge already deducts actual funding, equipment payments,
        # and outside expenses, and adds documented reserve coverage once.
        funding = {'repair': ZERO, 'capital': ZERO}
        for event in closing['events']:
            if event.kind == 'reserve' and event.id in closing['active_event_ids'] and start <= event.effective_date <= end:
                p = event.payload
                if p['pair_id'] == i and not p.get('opening'):
                    funding[p['purpose']] += max(D(p['amount']), ZERO)
        funded = sum(funding.values(), ZERO)
        additional = max(repair_target - funding['repair'], ZERO) + max(capital_target - funding['capital'], ZERO)
        posted_legacy = {s.get('legacy_id') for p in report['pairs'] for s in p['settlements']}
        saved_rows = [r for r in report['legacy_comparison']['rows'] if r['asset_id'] == i and r['legacy_id'] not in posted_legacy and r['date'] <= end.isoformat()]
        saved_remainder = sum((D(r['settlement_remainder']) for r in saved_rows), ZERO)
        subtotal = D(score['retained']) + saved_remainder - additional
        if any(D(saved[a]['original_loan']) > 0 for a in pair['asset_ids'] if a in saved):
            issues.append('Saved loan terms are available. Earnings-based payoff forecasts do not establish actual period payments.')
        if not pair['trailer_ids'] and assets[i].default_trailer_id:
            issues.append('A default trailer is saved, but this period needs a dated assignment before combining its targets.')
        if report['owner_insights']['unposted_in_period']:
            issues.append('Unposted saved settlement amounts are included as unverified management history, not posted accounting revenue.')
        pair_rows.append({'asset_id': i, 'name': pair['name'], 'asset_ids': pair['asset_ids'],
                         'recorded_retained': score['retained'], 'saved_remainder': money(saved_remainder), 'saved_settlement_ids': [r['legacy_id'] for r in saved_rows], 'repair_target': money(repair_target),
                         'capital_target': money(capital_target), 'already_funded': money(funded),
                         'additional_protection': money(additional), 'planning_subtotal': money(subtotal),
                         'issues': issues, 'bridge': score['bridge'] + [{'label': 'Saved settlements not yet posted (unverified)', 'amount': money(saved_remainder)}]})
    return {'version': 1, 'basis': 'calendar_day_planning_using_current_saved_vehicle_settings',
            'period': report['period'], 'as_of': report['as_of'], 'status': 'provisional',
            'settings': [{k: v for k, v in p.items() if not k.startswith('_')} for p in saved.values()],
            'pairs': pair_rows, 'planning_subtotal': money(sum((D(p['planning_subtotal']) for p in pair_rows), ZERO)),
            'unassigned_result': report['retention']['unassigned_asset_result'],
            'note': 'Planning estimate using current vehicle settings, not a historical funded balance. Recorded expenses, payments and funding are included once. Missing costs, financing and capital plans remain unresolved; this is not verified take-home or cash available to withdraw.'}
