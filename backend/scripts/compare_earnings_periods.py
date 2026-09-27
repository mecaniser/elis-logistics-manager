"""Read-only check of planning totals across adjacent calendar periods.

Run with the intended DATABASE_URL and --tenant/--start/--end. Output may contain
private financial totals; save it outside version control.
"""
import argparse
import calendar
import json
from datetime import date, timedelta
from decimal import Decimal
from app.database import SessionLocal
from app.services.finance import report, money


def compare(db, tenant, start, end):
    whole = report(db, tenant, start, end, end)
    segments = []
    current = start
    while current <= end:
        last = min(end, date(current.year, current.month, calendar.monthrange(current.year, current.month)[1]))
        part = report(db, tenant, current, last, last)
        segments.append({'start': str(current), 'end': str(last), 'pairs': part['earnings_plan']['pairs']})
        current = last + timedelta(days=1)
    pairs = []
    for row in whole['earnings_plan']['pairs']:
        summed = sum((Decimal(p['planning_subtotal']) for segment in segments for p in segment['pairs'] if p['asset_id'] == row['asset_id']), Decimal('0'))
        pairs.append({'asset_id': row['asset_id'], 'whole_period': row['planning_subtotal'], 'sum_of_months': money(summed), 'difference': money(Decimal(row['planning_subtotal']) - summed), 'issues': row['issues']})
    return {'tenant_id': tenant, 'start': str(start), 'end': str(end), 'basis': whole['earnings_plan']['basis'], 'read_only': True, 'pairs': pairs, 'months': segments, 'passes_period_additivity': all(Decimal(p['difference']) == 0 for p in pairs)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', required=True, type=int)
    parser.add_argument('--start', required=True, type=date.fromisoformat)
    parser.add_argument('--end', required=True, type=date.fromisoformat)
    args = parser.parse_args()
    if args.start > args.end:
        parser.error('start must not follow end')
    with SessionLocal() as db:
        result = compare(db, args.tenant, args.start, args.end)
        db.rollback()
    print(json.dumps(result, indent=2))
