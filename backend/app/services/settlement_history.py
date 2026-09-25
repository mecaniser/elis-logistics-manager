"""Read-only historical reconciliation. Source checks never silently rewrite books."""
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.models.finance import FinanceEvidence
from app.services.finance import D, money, ZERO

VERSION = 'settlement-review-v2'


def review_rows(records, sources):
    rows = []
    hashes = Counter(sources.get(r['id'], {}).get('sha256') for r in records if not r.get('source_settlement_id'))
    load_counts = Counter((r.get('settlement_type'), l['load_id']) for r in records if not r.get('source_settlement_id') for l in (sources.get(r['id'], {}).get('proposal') or {}).get('loads', []))
    for r in records:
        if r.get('source_settlement_id'):
            continue
        source = sources.get(r['id']) or {}
        p = source.get('proposal') or {}
        original = bool(source.get('id'))
        issues = []
        def flag(code, title, detail, amount=None):
            issues.append({'code': code, 'title': title, 'detail': detail, 'amount': money(amount) if amount is not None else None})
        # Stored fields are displayed for investigation but are not promoted to verified source facts.
        categories = {k: money(v) for k, v in (r.get('expense_categories') or {}).items() if v is not None}
        gross = (r.get('overview_amounts') or {}).get('gross_before_dispatch')
        carrier = (r.get('overview_amounts') or {}).get('dispatch_fee')
        remainder = r.get('cash_settlement_amount')
        miles, basis, gallons, calculated, delta = None, 'unverified', None, None, None
        verified = False
        differences = []
        if p:
            gross, carrier, categories, remainder = p['freight_gross'], p['carrier_retention'], p['deductions'], p['reported_payout']
            calculated = D(gross) - D(carrier) - sum((D(v) for v in categories.values()), ZERO) + D(p.get('cash_adjustments', 0))
            delta = D(remainder) - calculated
            loads, fuel = p.get('loads') or [], p.get('fuel') or []
            if delta:
                flag('payout_difference', 'Payout does not reconcile', 'Reported payout differs from freight less carrier and itemized deductions, including cash adjustments.', delta)
            if loads and sum((D(l['freight_gross']) for l in loads), ZERO) != D(gross):
                flag('load_total', 'Load revenue differs from statement total', 'Review all load rows and adjustments in the original.')
            if fuel and sum((D(f['amount']) for f in fuel), ZERO) != D(categories.get('fuel', 0)):
                flag('fuel_total', 'Fuel rows differ from fuel deduction', 'Review missing rows, refunds and fuel credits in the original.')
            if D(gross) > 0 and not loads:
                flag('load_total', 'Load rows need verification', 'The statement total has no normalized load rows to reconcile.')
            if D(categories.get('fuel', 0)) and not fuel and p.get('fuel_detail_status') != 'summary_only':
                flag('fuel_total', 'Fuel rows need verification', 'The fuel deduction has no normalized purchase rows.')
            if p.get('fuel_detail_status') == 'summary_only':
                flag('fuel_detail', 'Fuel detail and distance unavailable', 'The statement gives a fuel dollar total but no verified gallons or mileage. No consumption or fuel-per-mile result can be established.')
            if loads and all(l.get('driver_pay') is not None for l in loads) and sum((D(l['driver_pay']) for l in loads), ZERO) != D(categories.get('driver_pay', 0)):
                flag('source_row_review', 'Source-row amount needs review', 'Row amounts do not reconcile to the summary. Blank columns can shift extracted amounts; compare the driver and fuel columns in the original PDF.')
            if source.get('sha256') and hashes[source['sha256']] > 1:
                flag('duplicate_source', 'Original is shared by multiple records', 'Review a possible multi-truck statement, duplicate upload or amendment before posting.')
            if any(load_counts[(r.get('settlement_type'), l['load_id'])] > 1 for l in loads):
                flag('repeated_load', 'Load appears on another settlement', 'Compare originals to distinguish a correction, shared load or duplicate payment.')
            verified = not any(x['code'] in ('payout_difference', 'load_total', 'fuel_total', 'source_row_review', 'duplicate_source', 'repeated_load') for x in issues)
            if p.get('mileage_basis') in ('reported', 'independent') and D(p.get('miles') or 0) > 0:
                if loads and sum((D(l['empty_miles'])+D(l['loaded_miles']) for l in loads), ZERO) == D(p['miles']):
                    miles, basis = money(p['miles']), p['mileage_basis']
                else:
                    flag('mileage_total', 'Mileage needs row reconciliation', 'Load-row distance does not establish the reported total; per-mile conclusions are withheld.')
            gallons = money(sum((D(f['gallons']) for f in fuel if f.get('gallons') is not None), ZERO)) if fuel and all(f.get('gallons') is not None for f in fuel) else None
            late = [l['load_id'] for l in loads if l['delivery'] > r['settlement_date']]
            if late:
                flag('service_date', 'Delivery after statement date', 'Review service dates for load(s) ' + ', '.join(late) + ' before finalizing period earnings.')
            if any(f['product'] == 'unknown' for f in fuel):
                flag('fuel_product', 'Fuel product needs confirmation', 'Gallons purchased include unclassified products. Diesel consumption and measured MPG are not established.')
            mapped_old = dict(r.get('expense_categories') or {})
            old_gross = (r.get('overview_amounts') or {}).get('gross_before_dispatch')
            if p.get('mapping') == '277-paystub-review-v1':
                old_gross = r.get('gross_revenue')
                mapped_old.pop('dispatch_fee', None)
                mapped_old['other_deductions'] = mapped_old.pop('custom', 0)
            old = {'freight_gross': old_gross, 'reported_payout': r.get('cash_settlement_amount'), 'miles': r.get('miles_driven')}
            for field, value in old.items():
                if value is not None and p.get(field) is not None and D(money(value)) != D(money(p[field])):
                    differences.append({'field': field, 'stored': money(value), 'source': money(p[field]), 'difference': money(D(p[field])-D(value))})
            for k in set(categories) | set(mapped_old):
                if k == 'fleet_manager_support': continue
                oldval = mapped_old.get('fleet_manager_support' if k == 'support' else k, 0)
                if D(money(oldval or 0)) != D(money(categories.get(k, 0))):
                    differences.append({'field': k, 'stored': money(oldval or 0), 'source': money(categories.get(k, 0)), 'difference': money(D(categories.get(k, 0))-D(oldval or 0))})
            if differences:
                allocations = D(r.get('trailer_income_split_amount')) + D(r.get('repair_reserve_amount'))
                expected = all(d['field']=='loan_interest' or (d['field']=='freight_gross' and D(d['difference'])==allocations) for d in differences)
                if expected:
                    flag('interpretation_change', 'Planning amounts separated from statement figures', 'The prior application deducted internal reserves or modeled interest. These are explained presentation differences, not evidence of missing income.')
                else:
                    flag('stored_difference', 'Saved figures differ from original', 'Review the field-by-field differences. The saved record has not been changed.')
        elif original:
            flag('mapping', 'Original needs a reviewed mapping', 'The PDF is preserved. Its older layout has not passed the normalized load, fuel and payout checks.')
        else:
            flag('missing_source', 'Original PDF not available', 'Stored figures remain visible; upload the original to verify them.')
        # Internal allocation and reserve amounts are recorded as planning movements, not external costs.
        row = {'id': r['id'], 'asset_id': r['truck_id'], 'name': r['name'], 'date': r['settlement_date'], 'provider': ('277 Logistics' if p.get('mapping') == '277-paystub-review-v1' else r.get('settlement_type') or 'Unspecified'), 'status': 'arithmetic_matched' if verified else ('needs_review' if original else 'missing_source'), 'evidence_id': source.get('id'), 'sha256': source.get('sha256'), 'basis': 'source_statement' if p else 'stored_unverified', 'source_ref': p.get('source_ref'), 'freight': money(gross) if gross is not None else None, 'carrier': money(carrier) if carrier is not None else None, 'driver_pay': categories.get('driver_pay'), 'fuel': categories.get('fuel'), 'categories': categories, 'remainder': money(remainder) if remainder is not None else None, 'calculated_remainder': money(calculated) if calculated is not None else None, 'difference': money(delta) if delta is not None else None, 'miles': miles, 'stored_miles': money(r['miles_driven']) if r.get('miles_driven') is not None else None, 'mileage_basis': basis, 'gallons_purchased': gallons, 'measured_mpg': None, 'fuel_per_mile': str((D(categories.get('fuel', 0))/D(miles)).quantize(Decimal('.001'))) if miles and verified else None, 'driver_percent': str((D(categories['driver_pay'])/D(gross)*100).quantize(Decimal('.01'))) if gross and D(gross)>0 and categories.get('driver_pay') is not None else None, 'trailer_allocation': money(r.get('trailer_income_split_amount') or 0), 'repair_target': money(r.get('repair_reserve_amount') or 0), 'legacy_net': money(r['net_profit']) if r.get('net_profit') is not None else None, 'loads': p.get('loads') or [], 'fuel_rows': p.get('fuel') or [], 'differences': differences, 'issues': issues, 'deposit_status': 'not_reconciled', 'driver_payment_status': 'statement_amount_only'}
        rows.append(row)
    # Rolling purchase-based comparison: same truck/provider, supported statement miles,
    # minimum 3 records, and 28-calendar-day windows. Never label this consumption.
    groups = defaultdict(list)
    for r in sorted(rows, key=lambda x: (x['date'], x['id'])):
        key = (r['asset_id'], r['provider'])
        history = groups[key]
        day = date.fromisoformat(r['date'])
        current = [x for x in history if day-timedelta(days=27) <= date.fromisoformat(x['date'])] + [r]
        previous = [x for x in history if day-timedelta(days=55) <= date.fromisoformat(x['date']) <= day-timedelta(days=28)]
        def rate(window):
            if len(window)<3 or any(x['fuel_per_mile'] is None for x in window): return None
            return sum((D(x['fuel'] or 0) for x in window), ZERO)/sum((D(x['miles']) for x in window), ZERO)
        now, before = rate(current), rate(previous)
        r['rolling_fuel_per_mile'] = str(now.quantize(Decimal('.001'))) if now is not None else None
        if now is not None and before and now > before * Decimal('1.10'):
            change = (now/before-1)*100
            r['issues'].append({'code': 'fuel_spending', 'title': f'28-day fuel cost/mile up {change:.1f}%', 'detail': 'Compared with the previous 28-day statement window for this truck and carrier. Review fuel prices, purchase timing, routes and mileage coverage; this is not measured fuel consumption.', 'amount': money((now-before)*sum((D(x['miles']) for x in current),ZERO))})
        earlier = [x for x in history[-8:] if x['status']=='arithmetic_matched' and x['driver_percent'] is not None]
        if r['status']=='arithmetic_matched' and r['driver_percent'] is not None and len(earlier)>=4:
            baseline = median(D(x['driver_percent']) for x in earlier)
            if abs(D(r['driver_percent'])-baseline)>Decimal('2'):
                r['issues'].append({'code': 'driver_rate', 'title': 'Driver share differs from recent history', 'detail': f"Statement driver share {r['driver_percent']}% versus prior median {baseline}%. Check the driver agreement, adjustments and who drove these loads.", 'amount': None})
        peers = [x for x in history[-8:] if x['status']=='arithmetic_matched']
        if r['status']=='arithmetic_matched' and len(peers)>=4:
            for category, amount in r['categories'].items():
                if category in ('fuel','driver_pay') or D(amount)<=0: continue
                baseline = median(D(x['categories'].get(category, 0)) for x in peers)
                if D(amount)-baseline >= 100 and D(amount)>baseline*Decimal('1.5'):
                    r['issues'].append({'code':'expense_spike','title':f"Unusual {category.replace('_', ' ')} charge",'detail':f"Statement charge {money(amount)} USD versus prior same-truck, same-carrier median {money(baseline)} USD across {len(peers)} records. Verify the invoice or carrier agreement; this may be a valid one-time cost.",'amount':money(D(amount)-baseline)})
        history.append(r)
    return sorted(rows, key=lambda r:(r['date'],r['id']), reverse=True)


def settlement_history(db, tenant):
    records = db.query(Settlement, Truck).join(Truck, Settlement.truck_id==Truck.id).filter(Truck.tenant_id==tenant).all()
    evidence = db.query(FinanceEvidence.id, FinanceEvidence.source_key, FinanceEvidence.sha256, FinanceEvidence.extracted, FinanceEvidence.supersedes_id, FinanceEvidence.created_at).filter(FinanceEvidence.tenant_id==tenant).all()
    sources = {}
    amendments = {e.supersedes_id: e for e in evidence if e.supersedes_id}
    for e in evidence:
        ids = e.extracted.get('legacy_ids') or []
        if e.source_key.startswith('legacy-settlement:'):
            try: ids = [*ids, int(e.source_key.split(':')[1])]
            except ValueError: pass
        latest = e
        seen = set()
        while latest.id in amendments and latest.id not in seen:
            seen.add(latest.id)
            latest = amendments[latest.id]
        proposal = latest.extracted.get('proposal')
        if not proposal:
            from app.services.settlement_evidence import normalize_277_review
            proposal = normalize_277_review('\n'.join(p['text'] for p in latest.extracted.get('pages', [])))
        for i in ids: sources[i]={'id':latest.id,'sha256':latest.sha256,'proposal':proposal}
    data=[{**{c.name: getattr(s,c.name) for c in Settlement.__table__.columns}, 'name':t.name,'settlement_date':s.settlement_date.isoformat()} for s,t in records]
    rows=review_rows(data,sources)
    return {'version':VERSION,'tenant_id':tenant,'basis':'settlement_statement_date','evidence_status':'review_in_progress','period':{'start':min((r['date'] for r in rows),default=None),'end':max((r['date'] for r in rows),default=None)},'coverage':{'source_records':len(rows),'derived_allocations_excluded':sum(bool(r['source_settlement_id']) for r in data),'originals_preserved':sum(bool(r['evidence_id']) for r in rows),'arithmetic_matched':sum(r['status']=='arithmetic_matched' for r in rows),'originals_need_review':sum(x['status']=='needs_review' for x in rows),'needs_mapping':sum(r['basis']=='stored_unverified' and bool(r['evidence_id']) for r in rows),'missing_sources':sum(not r['evidence_id'] for r in rows),'flagged_records':sum(bool(r['issues']) for r in rows),'issue_counts':dict(Counter(i['code'] for r in rows for i in r['issues']))},'rows':rows,'limitations':['Arithmetic matching is not proof of deposit or driver receipt.','Older unmapped statements remain unverified. Internal trailer allocations are excluded from freight totals.','Fuel purchases are not consumption. Independent distance, product classification and tank timing remain necessary.','Missing income is not established without completed-load and payment evidence.']}
