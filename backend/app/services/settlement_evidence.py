"""Lossless 77 Cargo normalization for review; product classification is explicit."""
import re
from app.services.finance import money, D
from app.utils.pdf_parser import _parse_77_cargo_pdf, _extract_77_cargo_load_rows, _extract_77_cargo_sections, _parse_short_date


def normalize_77(text, evidence_id=''):
    parsed = _parse_77_cargo_pdf(text)
    raw_loads = _extract_77_cargo_load_rows(text)
    loads = []
    for row in raw_loads:
        loads.append({'load_id': row['load_id'], 'pickup': _parse_short_date(row['pickup']).isoformat(), 'delivery': _parse_short_date(row['delivery']).isoformat(), 'empty_miles': row['empty_miles'], 'loaded_miles': row['loaded_miles'], 'freight_gross': money(row['rate_amount'].replace(',', '')), 'source_row': ' | '.join(row.values())})
    fuel = []
    for section in _extract_77_cargo_sections(text, 'Fuel'):
        for raw in section.splitlines():
            m = re.match(r'^\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(.+?)\s+-?\$([\d,]+\.\d{2})\s*$', raw)
            if not m: continue
            gallons = re.search(r'Gallons\s*-\s*([\d.]+)', m[2], re.I)
            discount = re.search(r'Disc\s*-\s*\$([\d,.]+)', m[2], re.I)
            product = 'def' if re.search(r'\bDEF\b', m[2], re.I) else ('diesel' if re.search(r'\bdiesel\b', m[2], re.I) else 'unknown')
            fuel.append({'date': _parse_short_date(m[1]).isoformat(), 'gallons': gallons[1] if gallons else None, 'amount': money(m[3].replace(',', '')), 'discount': money(discount[1].replace(',', '')) if discount else None, 'product': product, 'location': m[2].split('/')[0].strip(), 'source_row': raw.strip()})
    overview = parsed.get('overview_amounts') or {}
    gross = D(overview.get('gross_before_dispatch', parsed['gross_revenue']))
    deductions = {('support' if k == 'fleet_manager_support' else k): money(v) for k, v in (parsed.get('expense_categories') or {}).items()}
    source_match = re.search(r'Settlement\s*#\s*(\d+)', text, re.I)
    adjustments = sum((D(x.get('amount', 0)) for x in parsed.get('cash_adjustments') or []), D(0))
    payout = parsed.get('cash_settlement_amount')
    if payout is None: payout = parsed['net_profit']
    return {'kind': 'settlement', 'evidence_id': evidence_id, 'source_ref': f"77cargo:{source_match[1]}" if source_match else '', 'period_start': str(parsed['week_start']), 'period_end': str(parsed['week_end']), 'freight_gross': money(gross), 'carrier_retention': money(gross - D(parsed['gross_revenue'])), 'deductions': deductions, 'reported_payout': money(payout), 'cash_adjustments': money(adjustments), 'miles': str(parsed['miles_driven']), 'mileage_basis': 'reported', 'fuel': fuel, 'loads': loads}


def normalize_277_review(text):
    """Strict summary + load mapping for the 277 paystub. Review only, not posting.

    These sources do not state odometer distance or diesel gallons. Never borrow
    the legacy application's fuel-derived mileage estimates into this mapping.
    """
    if not ('277 Logistics' in text or re.search(r'Payee.*\b277\b', text)) or 'Pay Amount' not in text:
        return None
    fields = {'Gross Pay':'gross', 'Dispatch Fee':'carrier', "Driver's Pay":'driver_pay', "Driver's Pay Fee":'payroll_fee', 'Fuel':'fuel', 'IFTA':'ifta', 'Safety':'safety', 'Prepass':'prepass', 'Insurance':'insurance', 'Reimbursment':'reimbursement', 'Bonus':'bonus', 'Deductions':'other_deductions', 'Net Pay':'net'}
    values = {}
    for label, key in fields.items():
        found = re.findall(r'^' + re.escape(label) + r'\s+(-?)\$([\d,]+\.\d{2})\s*$', text, re.M)
        if len(found) != 1: return None
        values[key] = money(found[0][0] + found[0][1].replace(',', ''))
    period = re.search(r'Pay Period:\s*(\d{1,2}/\d{1,2}/\d{4})', text)
    if not period: return None
    end = _parse_short_date(period[1]).isoformat()
    loads = []
    for raw in text.splitlines():
        match = re.search(r'(B-[A-Z0-9]+).*?(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+\$([\d,]+\.\d{2})\s+\$([\d,]+\.\d{2})', raw)
        if not match: continue
        loads.append({'load_id':match[1], 'pickup':_parse_short_date(match[2]).isoformat(), 'delivery':_parse_short_date(match[3]).isoformat(), 'empty_miles':None, 'loaded_miles':None, 'freight_gross':money(match[5].replace(',','')), 'driver_pay':money(match[6].replace(',','')), 'source_row':raw})
    deductions = {k:v for k,v in values.items() if k not in ('gross','carrier','net','reimbursement','bonus')}
    for k in ('reimbursement','bonus'):
        if D(values[k]): deductions[k] = money(-D(values[k]))
    return {'source_ref':f'277:{end}', 'period_start':min((l['pickup'] for l in loads),default=end), 'period_end':end, 'freight_gross':values['gross'], 'carrier_retention':values['carrier'], 'deductions':deductions, 'reported_payout':values['net'], 'cash_adjustments':'0.00', 'miles':None, 'mileage_basis':'unverified', 'loads':loads, 'fuel':[], 'fuel_detail_status':'summary_only', 'mapping':'277-paystub-review-v1'}
