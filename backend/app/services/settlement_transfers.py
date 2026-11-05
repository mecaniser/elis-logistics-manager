"""Read-only reporting of explicit cross-truck carryovers; never changes saved books."""
from collections import defaultdict
from decimal import Decimal
import re
from types import SimpleNamespace

REFERENCE = re.compile(r'\bcarryover\s+adjustment\s*:\s*settlement\s*#\s*(\d+)\b', re.I)
ZERO = Decimal('0.00')


def amount(value):
    return Decimal(str(value or 0)).quantize(Decimal('0.01'))


def transfer_reference(description):
    match = REFERENCE.search(description or '')
    return match[1] if match else None


def transfer_entries(record):
    """Recognize only explicit references, never infer transfers from equal amounts."""
    get = record.get if isinstance(record, dict) else lambda key, default=None: getattr(record, key, default)
    entries = []
    for field, sign in [('deduction_details', -1), ('reimbursement_details', 1), ('cash_adjustments', 1)]:
        for item in get(field, None) or []:
            reference = transfer_reference(item.get('description'))
            if reference:
                entries.append({'reference': reference, 'amount': amount(item.get('amount')) * sign, 'field': field})
    return entries


def reporting(record):
    get = record.get if isinstance(record, dict) else lambda key, default=None: getattr(record, key, default)
    entries = transfer_entries(record)
    # Old imports booked transfer debits as costs and credits as reimbursements.
    legacy_debits = -sum((e['amount'] for e in entries if e['field'] == 'deduction_details'), ZERO)
    legacy_credits = sum((e['amount'] for e in entries if e['field'] == 'reimbursement_details'), ZERO)
    transfer = sum((e['amount'] for e in entries), ZERO)
    other_adjustments = sum((amount(item.get('amount')) for item in get('cash_adjustments') or []
                             if not transfer_reference(item.get('description'))), ZERO)
    categories = dict(get('expense_categories') or {})
    # A description alone is insufficient: require its amount in the recorded category.
    duplicate_entries = len({(e['reference'], e['amount']) for e in entries}) != len(entries)
    if (duplicate_entries or legacy_debits < 0 or legacy_credits < 0
            or legacy_debits > amount(categories.get('deduct')) or legacy_credits > amount(categories.get('reimbursement'))):
        return {'operating_expenses': get('expenses'), 'operating_net': get('net_profit'),
                'settlement_net': get('net_profit'), 'transfer': ZERO, 'other_cash_adjustment': ZERO, 'categories': categories,
                'entries': entries, 'review_required': True}
    if legacy_debits:
        categories['deduct'] = float(amount(categories.get('deduct')) - legacy_debits)
    if legacy_credits:
        categories['reimbursement'] = float(amount(categories.get('reimbursement')) - legacy_credits)
    operating_net = amount(get('net_profit')) + legacy_debits if get('net_profit') is not None else None
    return {'operating_expenses': amount(get('expenses')) - legacy_debits if get('expenses') is not None else None,
            'operating_net': operating_net,
            'settlement_net': operating_net + transfer + other_adjustments if operating_net is not None else None,
            'transfer': transfer, 'other_cash_adjustment': other_adjustments, 'categories': categories, 'entries': entries, 'review_required': False}


def reporting_record(record):
    """Detached value object so SQLAlchemy cannot flush reporting corrections."""
    values = {c.name: getattr(record, c.name) for c in record.__table__.columns}
    result = reporting(record)
    return SimpleNamespace(**{**values, 'expenses': result['operating_expenses'],
                             'net_profit': result['settlement_net'], 'expense_categories': result['categories'],
                             'operating_net_profit': result['operating_net'], 'cross_truck_transfer': result['transfer'],
                             'other_cash_adjustment': result['other_cash_adjustment']})


def audit_transfers(records):
    groups = defaultdict(list)
    unlinked = []
    for record in records:
        get = record.get if isinstance(record, dict) else lambda key, default=None: getattr(record, key, default)
        if get('source_settlement_id'):
            continue
        result = reporting(record)
        for item in get('cash_adjustments') or []:
            if not transfer_reference(item.get('description')):
                unlinked.append({'tenant_id': get('tenant_id'), 'date': str(get('settlement_date')),
                                 'provider': get('settlement_type'), 'reference': None, 'status': 'needs_review',
                                 'entries': [{'settlement_id': get('id'), 'truck_id': get('truck_id'),
                                              'amount': str(amount(item.get('amount'))), 'field': 'cash_adjustments',
                                              'classification_review': True}]})
        for entry in result['entries']:
            # Never match across businesses, dates or providers.
            key = (get('tenant_id'), str(get('settlement_date')), str(get('settlement_type')), entry['reference'])
            groups[key].append({'settlement_id': get('id'), 'truck_id': get('truck_id'),
                                'amount': str(entry['amount']), 'field': entry['field'],
                                'classification_review': result['review_required']})
    rows = []
    for (tenant, day, provider, reference), entries in sorted(groups.items(), key=lambda item: str(item[0])):
        matched = (len(entries) == 2 and len({e['truck_id'] for e in entries}) == 2
                   and sum((amount(e['amount']) for e in entries), ZERO) == ZERO
                   and any(amount(e['amount']) > 0 for e in entries)
                   and not any(e['classification_review'] for e in entries))
        rows.append({'tenant_id': tenant, 'date': day, 'provider': provider, 'reference': reference,
                     'status': 'matched' if matched else 'needs_review', 'entries': entries})
    return rows + unlinked
