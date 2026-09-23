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
