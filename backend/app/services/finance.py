"""Reconciled finance engine. Helpers flush; the router owns every transaction."""
import base64
import csv
import hashlib
import io
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException
from sqlalchemy import select
from app.models.finance import FinanceEvent, FinanceEvidence, FinancePosting, FinanceLine, FinanceReport
from app.models.truck import Truck
from app.models.tenant import Tenant

ZERO = Decimal('0.00')
ACCOUNTS = {
    'cash': 'asset', 'receivable': 'asset', 'equipment': 'asset',
    'accumulated_depreciation': 'contra_asset', 'payable': 'liability',
    'card_payable': 'liability', 'owner_advance': 'liability',
    'owner_equity': 'equity', 'owner_draw': 'contra_equity',
    'freight': 'revenue', 'other_income': 'revenue', 'disposal_gain': 'revenue',
    'carrier': 'expense', 'driver_pay': 'expense', 'fuel': 'expense',
    'insurance': 'expense', 'tolls': 'expense', 'support': 'expense',
    'repairs': 'expense', 'overhead': 'expense', 'interest': 'expense',
    'depreciation': 'expense', 'other_expense': 'expense',
}
EXPENSE_MAP = {'fleet_manager_support': 'support', 'loan_interest': 'interest', 'service_on_truck': 'repairs'}


def D(value):
    return Decimal(str(value if value is not None else 0))


def money(value):
    return str(D(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def fail(message, code='INVALID_OPERATION', status=409):
    raise HTTPException(status_code=status, detail={'code': code, 'message': message})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def events(db, tenant, as_of=None):
    q = db.query(FinanceEvent).filter(FinanceEvent.tenant_id == tenant)
    if as_of:
        q = q.filter(FinanceEvent.effective_date <= as_of)
    return q.order_by(FinanceEvent.effective_date, FinanceEvent.sequence).all()


def evidence(db, tenant, key):
    item = db.query(FinanceEvidence).filter_by(tenant_id=tenant, id=key).first()
    if not item:
        fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
    return item


def resource(db, tenant, key, kinds=None):
    item = db.query(FinanceEvent).filter_by(tenant_id=tenant, id=key).first()
    if not item:
        fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
    if kinds and item.kind not in kinds:
        fail('The referenced record has the wrong type.')
    return item


def line(account, amount, asset=None):
    value = D(amount)
    return {'account': account, 'debit': max(value, ZERO), 'credit': max(-value, ZERO), 'asset_id': asset}


def post(db, tenant, event, description, lines, reversal_of=None):
    if not lines:
        return
    if sum(D(l['debit']) - D(l['credit']) for l in lines) != ZERO:
        fail('Debits and credits must balance exactly.', 'UNBALANCED_POSTING')
    for l in lines:
        if l['account'] not in ACCOUNTS or D(l['debit']) < 0 or D(l['credit']) < 0 or (D(l['debit']) and D(l['credit'])):
            fail('Invalid account or debit/credit line.')
    posting = FinancePosting(tenant_id=tenant, event_id=event.id, entry_date=event.effective_date, description=description, reversal_of=reversal_of)
    db.add(posting)
    db.flush()
    for l in lines:
        db.add(FinanceLine(posting_id=posting.id, **l))
    db.flush()


def state(db, tenant, as_of):
    es = events(db, tenant, as_of)
    result = {'events': es, 'accounts': {}, 'statements': {}, 'transactions': {}, 'matches': {}, 'allocated': {}, 'claims': {}, 'reserves': {}, 'plans': {}, 'policy': None, 'commitments': [], 'assignments': [], 'settlements': [], 'disposals': {}}
    reversed_events = {p.event_id for p in db.query(FinancePosting).filter(FinancePosting.tenant_id == tenant, FinancePosting.id.in_([e.payload['posting_id'] for e in es if e.kind == 'reversal'])).all()}
    for e in es:
        if e.id in reversed_events:
            continue
        p = e.payload
        k = e.kind
        if k == 'policy': result['policy'] = p
        elif k == 'account': result['accounts'][e.id] = p
        elif k == 'statement':
            if p.get('supersedes_id'): result['statements'].pop(p['supersedes_id'], None)
            result['statements'][e.id] = {**p, 'id': e.id}
        elif k in ('bill', 'owner_advance'):
            result['claims'][e.id] = {**p, 'id': e.id, 'remaining': D(p['amount']), 'creditor': 'owner' if k == 'owner_advance' else 'vendor'}
        elif k == 'reserve':
            key = f"{p['pair_id']}:{p['purpose']}:{p.get('asset_id') or ''}"
            r = result['reserves'].setdefault(key, {**p, 'id': e.id, 'balance': ZERO})
            r['balance'] += D(p['amount'])
        elif k == 'payment':
            claim = result['claims'].get(p['claim_id'])
            if not claim: continue
            amount = D(p['amount'])
            claim['remaining'] -= amount
            if p['payer'] == 'owner':
                # Substitution, not a second expense or a second claim on the same money.
                result['claims'][e.id] = {**claim, 'id': e.id, 'remaining': amount, 'creditor': 'owner', 'source_claim_id': p['claim_id']}
            else:
                for reserve in result['reserves'].values():
                    if reserve['id'] == claim.get('reserve_id'):
                        reserve['balance'] -= min(amount, max(reserve['balance'], ZERO))
                if p.get('transaction_id'): result['allocated'][p['transaction_id']] = result['allocated'].get(p['transaction_id'], ZERO) + amount
        elif k == 'credit_note':
            claim = result['claims'].get(p['claim_id'])
            if claim:
                if p.get('transaction_id'): result['matches'][p['transaction_id']] = e.id
                else: claim['remaining'] -= D(p['amount'])
                claim['credited'] = D(claim.get('credited', 0)) + D(p['amount'])
        elif k == 'bank_match':
            result['matches'][p['transaction_id']] = e.id
            if p.get('counterpart_transaction_id'): result['matches'][p['counterpart_transaction_id']] = e.id
        elif k == 'asset_plan': result['plans'][p['asset_id']] = {**p, 'id': e.id}
        elif k == 'disposal': result['disposals'][p['asset_id']] = p
        elif k == 'assignment':
            for prior in result['assignments']:
                if prior['id'] in p.get('_ends_assignment_ids', []): prior['end'] = (e.effective_date - timedelta(days=1)).isoformat()
            result['assignments'].append({**p, 'start': e.effective_date.isoformat(), 'id': e.id})
        elif k == 'settlement': result['settlements'].append({**p, 'id': e.id, 'date': e.effective_date.isoformat()})
        elif k == 'financing' and p['action'] == 'commitment': result['commitments'].append({**p, 'id': e.id})
    for s in result['statements'].values():
        for t in s['_transactions']:
            if date.fromisoformat(t['date']) <= as_of:
                old = result['transactions'].get(t['id'])
                if old and old != t: fail('Conflicting statement transactions require review.')
                result['transactions'][t['id']] = t
    for tid, amount in result['allocated'].items():
        if tid in result['transactions'] and amount == -D(result['transactions'][tid]['amount']): result['matches'][tid] = 'allocated_payments'
    result['active_event_ids'] = {e.id for e in es if e.id not in reversed_events}
    return result


def cash_position(db, tenant, as_of):
    s = state(db, tenant, as_of)
    coverage, cash, card = [], ZERO, ZERO
    issues = []
    for aid, a in s['accounts'].items():
        statements = [x for x in s['statements'].values() if x['account_id'] == aid and date.fromisoformat(x['end']) <= as_of]
        latest = max(statements, key=lambda x: x['end']) if statements else None
        coverage.append({'account_id': aid, 'name': a['name'], 'type': a['account_type'], 'reconciled_through': latest['end'] if latest else None, 'balance': latest['closing'] if latest else None})
        if not latest or latest['end'] != as_of.isoformat(): issues.append(f"{a['name']}: statement balance needed through {as_of}.")
        if latest:
            if a['account_type'] == 'bank': cash += D(latest['closing'])
            else: card += max(-D(latest['closing']), ZERO)
    if not s['accounts'] or not any(a['account_type'] == 'bank' for a in s['accounts'].values()): issues.append('Add and reconcile business bank accounts.')
    policy = s['policy'] or {}
    if any(tid not in s['matches'] for tid in s['transactions']): issues.append('Unmatched bank or card transactions may overlap unpaid obligations. Resolve them before relying on available cash.')
    if not policy.get('account_coverage_confirmed'): issues.append('Confirm all business bank and card accounts are included.')
    reserve_total = sum((max(r['balance'], ZERO) for r in s['reserves'].values()), ZERO)
    remaining_cover = {r['id']: max(r['balance'], ZERO) for r in s['reserves'].values()}
    unpaid = owner = ZERO
    protected_claims = []
    for c in s['claims'].values():
        outstanding = max(c['remaining'], ZERO)
        rid = c.get('reserve_id')
        covered = min(outstanding, remaining_cover.get(rid, ZERO))
        if rid: remaining_cover[rid] = remaining_cover.get(rid, ZERO) - covered
        uncovered = outstanding - covered
        if c['creditor'] == 'owner': owner += uncovered
        else: unpaid += uncovered
        if outstanding: protected_claims.append({'id': c['id'], 'description': c['description'], 'outstanding': money(outstanding), 'covered_by_reserve': money(covered), 'uncovered': money(uncovered), 'creditor': c['creditor']})
    committed = ZERO
    # A linked claim is already protected above. No unlinked commitment is accepted.
    for c in s['commitments']:
        if c.get('owner_claim_id') not in s['claims'] and c.get('due') and as_of <= date.fromisoformat(c['due']) <= as_of + timedelta(days=30):
            committed += D(c['business_amount'])
    available = cash - reserve_total - unpaid - owner - card - committed
    funding_ready = not issues
    for key, title in [('approved', 'Accounting policy'), ('opening_confirmed', 'Opening balances'), ('history_confirmed', 'Historical obligation coverage'), ('owner_treatment_confirmed', 'Owner funding treatment')]:
        if not policy.get(key): issues.append(f'{title} needs confirmation before available cash is final.')
    if reserve_total > max(cash, ZERO): issues.append('Protected reserve balances exceed reconciled cash; funding requires review.')
    has_bank_evidence = any(c['balance'] is not None and c['type'] == 'bank' for c in coverage)
    return {'as_of': as_of.isoformat(), 'currency': 'USD', 'basis': 'reconciled_cash_position', 'status': 'provisional' if issues else 'reconciled', 'funding_ready': funding_ready, 'available': money(available) if has_bank_evidence else None, 'business_cash': money(cash) if has_bank_evidence else None, 'protected_reserves': money(reserve_total), 'uncovered_bills': money(unpaid), 'owner_reimbursement': money(owner), 'card_obligations': money(card), 'committed_financing': money(committed), 'coverage': coverage, 'claims': protected_claims, 'issues': issues}


def parse_statement(db, tenant, p):
    a = resource(db, tenant, p['account_id'], {'account'})
    mapping = resource(db, tenant, p['mapping_id'], {'csv_mapping'}).payload
    doc = evidence(db, tenant, p['evidence_id'])
    try:
        reader = csv.DictReader(io.StringIO(base64.b64decode(doc.content_base64).decode('utf-8-sig')))
        required = [mapping[x] for x in ('date_column', 'amount_column', 'description_column', 'id_column')]
        if not reader.fieldnames or not all(x in reader.fieldnames for x in required): fail('CSV columns do not match the saved mapping.')
        txs, seen = [], set()
        for row_number, row in enumerate(reader, start=2):
            when = datetime.strptime(row[mapping['date_column']], mapping['date_format']).date()
            if not date.fromisoformat(p['start']) <= when <= date.fromisoformat(p['end']): fail(f'Row {row_number} is outside the statement period.')
            external_id = row[mapping['id_column']].strip()
            if not external_id or external_id in seen: fail(f'Row {row_number} needs a unique bank transaction ID.')
            seen.add(external_id)
            amount = D(row[mapping['amount_column']].replace(',', '').replace('$', '').strip())
            if not amount.is_finite() or amount != amount.quantize(Decimal('.01')): fail(f'Row {row_number} has an invalid currency amount.')
            if mapping['invert_sign']: amount = -amount
            txs.append({'id': hashlib.sha256(f'{a.id}:{external_id}'.encode()).hexdigest(), 'account_id': a.id, 'external_id': external_id, 'date': when.isoformat(), 'amount': money(amount), 'description': row[mapping['description_column']], 'evidence_id': doc.id, 'source_row': row_number})
    except (ValueError, UnicodeDecodeError, KeyError, ArithmeticError) as exc:
        fail(f'Cannot read statement CSV: {exc}')
    if date.fromisoformat(p['end']) < date.fromisoformat(p['start']): fail('Statement end precedes its start.')
    if D(p['opening']) + sum((D(t['amount']) for t in txs), ZERO) != D(p['closing']): fail('Opening balance plus transactions does not equal closing balance.', 'STATEMENT_UNBALANCED')
    return txs


def lock_business(db, tenant):
    # SQLite needs a real write transaction before reads; SELECT FOR UPDATE is a no-op there.
    if db.get_bind().dialect.name == 'sqlite':
        connection = db.connection()
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql('BEGIN IMMEDIATE')
    db.execute(select(Tenant).where(Tenant.id == tenant).with_for_update()).scalar_one()


def append_command(db, tenant, command, key):
    # Serialize writes for a business, including idempotency and closed-period checks.
    lock_business(db, tenant)
    data = command.model_dump(mode='json')
    # Preserve idempotency digests for commands saved before repair linking existed.
    if data['payload'].get('legacy_repair_id') is None:
        data['payload'].pop('legacy_repair_id', None)
    hash_value = digest(data)
    prior = db.query(FinanceEvent).filter_by(tenant_id=tenant, key=key).first()
    if prior:
        if prior.digest != hash_value: fail('Idempotency key was already used with different content.', 'IDEMPOTENCY_KEY_REUSED')
        return prior
    p = data['payload']
    k = p['kind']
    when = command.effective_date
    all_events = events(db, tenant)
    closed = {}
    for e in all_events:
        if e.kind in ('close_period', 'reopen_period'):
            closed[(e.payload['start'], e.payload['end'])] = e.kind == 'close_period'
    if k not in ('reopen_period', 'close_period') and any(active and start <= when.isoformat() <= end for (start, end), active in closed.items()):
        fail('This period is closed. Reopen it with a reason or post a dated correction.', 'PERIOD_CLOSED')
    for field in ('asset_id', 'truck_id', 'trailer_id', 'pair_id'):
        if p.get(field) is not None:
            asset = db.query(Truck).filter_by(id=p[field], tenant_id=tenant).first()
            if not asset: fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
            if field in ('truck_id', 'pair_id') and asset.vehicle_type != 'truck': fail('Pair must identify the power unit.')
            if field == 'trailer_id' and asset.vehicle_type != 'trailer': fail('Select a trailer.')
    for field in ('evidence_id', 'payoff_evidence_id'):
        if p.get(field):
            evidence(db, tenant, p[field])
            if db.query(FinanceEvidence).filter_by(tenant_id=tenant, supersedes_id=p[field]).first(): fail('This document was amended. Review its latest version before posting.', 'SUPERSEDED_EVIDENCE')
    for eid in p.get('evidence_ids', []): evidence(db, tenant, eid)
    s = state(db, tenant, when)
    bank_state = state(db, tenant, date.max)
    s['transactions'] = bank_state['transactions']
    s['matches'] = bank_state['matches']
    s['accounts'] = bank_state['accounts']
    s['allocated'] = bank_state['allocated']
    lines, description, reversal_of = [], k.replace('_', ' '), None
    if k == 'policy':
        try: ZoneInfo(p['timezone'])
        except ZoneInfoNotFoundError: fail('Choose a valid IANA timezone.')
        if any(p[x] for x in ('approved', 'opening_confirmed', 'history_confirmed', 'carrier_presentation_confirmed', 'owner_treatment_confirmed', 'depreciation_confirmed', 'tax_basis_confirmed')) and not p['evidence_ids']:
            fail('Attach supporting evidence before confirming accounting policy or opening history.')
    elif k == 'retention_targets':
        timezone = (bank_state['policy'] or {}).get('timezone', 'UTC')
        if when < datetime.now(ZoneInfo(timezone)).date():
            fail('Retention targets apply prospectively. Choose today or a future date.', 'RETROACTIVE_TARGET')
    elif k == 'statement':
        p['_transactions'] = parse_statement(db, tenant, p)
        if when.isoformat() != p['end']: fail('Statement effective date must equal statement end.')
        old = resource(db, tenant, p['supersedes_id'], {'statement'}) if p.get('supersedes_id') else None
        if old and old.payload['account_id'] != p['account_id']: fail('A replacement statement must use the same account.')
        if old and any(t['id'] in s['matches'] or s['allocated'].get(t['id']) for t in old.payload['_transactions']): fail('Matched statements cannot be replaced; record a supported correction.')
        for existing in bank_state['statements'].values():
            if existing['id'] != p.get('supersedes_id') and existing['account_id'] == p['account_id']:
                if {t['id'] for t in existing['_transactions']} & {t['id'] for t in p['_transactions']}: fail('Bank transaction IDs already appear in another statement.', 'DUPLICATE_TRANSACTION')
                if p['start'] <= existing['end'] and p['end'] >= existing['start']: fail('Statement periods overlap. Link the replacement explicitly.')
                if (date.fromisoformat(existing['end']) + timedelta(days=1)).isoformat() == p['start'] and D(existing['closing']) != D(p['opening']): fail('Opening does not match the preceding reconciled statement.')
    elif k in ('bill', 'owner_advance'):
        if p.get('legacy_repair_id'):
            from app.models.repair import Repair
            repair = db.query(Repair).join(Truck, Repair.truck_id == Truck.id).filter(Repair.id == p['legacy_repair_id'], Truck.tenant_id == tenant).first()
            if not repair: fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
            if p.get('asset_id') != repair.truck_id: fail('The obligation must reference the repair asset.')
            if any(e.kind in ('bill', 'owner_advance') and e.payload.get('legacy_repair_id') == repair.id for e in all_events):
                fail('This repair already has an obligation. Review its existing claim or correction.', 'DUPLICATE_REPAIR')
        if D(p['amount']) <= 0: fail('Amount must be greater than zero.')
        if any(e.kind in ('bill', 'owner_advance') and e.payload['source_ref'] == p['source_ref'] for e in all_events): fail('This obligation already exists.', 'DUPLICATE_SOURCE')
        if p.get('reserve_id'):
            reserve = next((r for r in s['reserves'].values() if r['id'] == p['reserve_id']), None)
            if not reserve or reserve['pair_id'] != p.get('pair_id'): fail('Reserve must belong to this earning pair.')
            if p['category'] != 'repairs' or reserve['purpose'] != 'repair': fail('Only repair reserves can cover repair bills.')
        if p['category'] in ('equipment', 'repairs') and not p.get('asset_id'): fail('Equipment acquisitions and repairs need the actual asset.')
        if p.get('reserve_id') and p['asset_id'] != p['pair_id'] and not any(a['truck_id'] == p['pair_id'] and a['trailer_id'] == p['asset_id'] and a['start'] <= when.isoformat() <= (a.get('end') or '9999-12-31') for a in s['assignments']): fail('The repair asset is not assigned to this reserve’s earning pair on the incurred date.')
        lines = [line(p['category'], p['amount'], p.get('asset_id')), line('payable' if k == 'bill' else 'owner_advance', -D(p['amount']), p.get('asset_id'))]
        description = p['description']
    elif k == 'payment':
        claim_event = resource(db, tenant, p['claim_id'], {'bill', 'owner_advance', 'payment'})
        claim = s['claims'].get(claim_event.id)
        if not claim or not ZERO < D(p['amount']) <= claim['remaining']: fail('Payment exceeds the outstanding claim or precedes it.')
        amount = D(p['amount'])
        if D(p['principal']) + D(p['interest']) not in (ZERO, amount): fail('Principal and interest must reconcile to the payment.')
        creditor = 'owner_advance' if claim['creditor'] == 'owner' else 'payable'
        if p['payer'] == 'owner':
            if claim['creditor'] == 'owner' or not p.get('evidence_id') or p.get('transaction_id'): fail('Owner payment needs evidence and an unpaid vendor bill.')
            credit = 'owner_advance'
        else:
            t = s['transactions'].get(p.get('transaction_id'))
            if not t or t['id'] in s['matches']: fail('Choose an unmatched reconciled transaction.')
            a = s['accounts'][t['account_id']]
            if (a['account_type'] == 'card') != (p['payer'] == 'card'): fail('Payment account type does not match payer.')
            if t['date'] != when.isoformat(): fail('Use the bank transaction date as the payment effective date.')
            if amount > -D(t['amount']) - s['allocated'].get(t['id'], ZERO): fail('Payment exceeds the unallocated bank/card transaction amount.')
            credit = 'card_payable' if p['payer'] == 'card' else 'cash'
        lines = [line(creditor, amount, claim.get('asset_id')), line(credit, -amount, claim.get('asset_id'))]
    elif k == 'credit_note':
        claim = s['claims'].get(p['claim_id'])
        if not claim: fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
        amount = D(p['amount'])
        if amount <= 0 or amount + D(claim.get('credited', 0)) > D(claim['amount']): fail('Credit exceeds the original obligation.')
        if p.get('transaction_id'):
            t = s['transactions'].get(p['transaction_id'])
            if not t or t['id'] in s['matches'] or t['date'] != when.isoformat() or D(t['amount']) != amount: fail('Refund must match one unallocated incoming transaction on its date.')
            if amount > D(claim['amount']) - claim['remaining'] - D(claim.get('credited', 0)): fail('Refund exceeds the previously paid cost.')
            debit_account = 'card_payable' if s['accounts'][t['account_id']]['account_type'] == 'card' else 'cash'
        else:
            if amount > claim['remaining']: fail('Credit exceeds unpaid balance; use a matched refund for paid amounts.')
            debit_account = 'owner_advance' if claim['creditor'] == 'owner' else 'payable'
        lines = [line(debit_account, amount, claim.get('asset_id')), line(claim['category'], -amount, claim.get('asset_id'))]
        description = p['description']
    elif k == 'bank_match':
        t = s['transactions'].get(p['transaction_id'])
        if not t or t['id'] in s['matches']: fail('Choose an unmatched reconciled transaction.')
        if s['accounts'][t['account_id']]['account_type'] != 'bank': fail('Start this match from a bank transaction.')
        if t['date'] != when.isoformat(): fail('Use the bank transaction date as the match effective date.')
        if s['allocated'].get(t['id'], ZERO): fail('This transaction already has partial bill allocations.')
        amount = D(t['amount'])
        mt = p['match_type']
        if mt in ('settlement', 'asset_sale'):
            settlement = resource(db, tenant, p.get('target_id'), {'settlement'} if mt == 'settlement' else {'disposal'})
            matched = sum((D(s['transactions'][e.payload['transaction_id']]['amount']) for e in s['events'] if e.kind == 'bank_match' and e.id in s['active_event_ids'] and e.payload.get('target_id') == settlement.id and e.payload['transaction_id'] in s['transactions']), ZERO)
            expected = D(settlement.payload['reported_payout']) if mt == 'settlement' else D(settlement.payload['gross_sale']) - D(settlement.payload['selling_costs'])
            remaining = expected - matched
            if not amount or amount * remaining <= 0 or abs(amount) > abs(remaining): fail('Transaction exceeds or has the wrong sign for the remaining receivable.')
            lines = [line('cash', amount), line('receivable', -amount, settlement.payload['asset_id'])]
        elif mt in ('owner_contribution', 'owner_distribution'):
            if (mt == 'owner_contribution' and amount <= 0) or (mt == 'owner_distribution' and amount >= 0): fail('Bank transaction has the wrong sign.')
            lines = [line('cash', amount), line('owner_equity' if mt == 'owner_contribution' else 'owner_draw', -amount)]
        else:
            other = s['transactions'].get(p.get('counterpart_transaction_id'))
            if not other or other['id'] in s['matches'] or s['allocated'].get(other['id'], ZERO) or other['account_id'] == t['account_id'] or D(other['amount']) != -amount: fail('Select the opposite, unmatched transaction in another account.')
            expected = 'card' if mt == 'card_repayment' else 'bank'
            if s['accounts'][other['account_id']]['account_type'] != expected: fail('Counterpart account type is incorrect.')
            if mt == 'card_repayment':
                if amount >= 0: fail('Card repayment must leave the bank account.')
                if sum((D(p[f'{bucket}_amount']) for bucket in ('operating', 'investing', 'financing')), ZERO) != -amount:
                    fail('Allocate the entire card repayment between operating, investing and financing cash flows using its supporting charges.')
                lines = [line('cash', amount), line('card_payable', -amount)]
    elif k == 'reserve':
        if p['purpose'] == 'capital' and not p.get('asset_id'): fail('Capital reserves require the asset whose acquisition is being recovered.')
        rkey = f"{p['pair_id']}:{p['purpose']}:{p.get('asset_id') or ''}"
        prior_balance = s['reserves'].get(rkey, {}).get('balance', ZERO)
        if prior_balance + D(p['amount']) < 0: fail('Reserve release exceeds its funded balance.')
        if D(p['amount']) > 0:
            cash = cash_position(db, tenant, when)
            if cash['available'] is None or not cash['funding_ready']: fail('Reconcile cash and account coverage before funding reserves.')
            if D(p['amount']) > max(D(cash['available']), ZERO): fail('Insufficient unrestricted cash to fund this reserve.')
            if p['purpose'] == 'capital' and not p['opening']:
                weekly = D((s['policy'] or {}).get('repair_weekly_target', '300.00'))
                funded_this_week = sum((D(e.payload['amount']) for e in s['events'] if e.kind == 'reserve' and e.payload['purpose'] == 'repair' and e.payload['pair_id'] == p['pair_id'] and e.effective_date >= when - timedelta(days=when.weekday())), ZERO)
                if funded_this_week < weekly: fail('Fund this pair’s weekly repair target before new capital allocations.')
    elif k == 'assignment':
        end = p.get('end') or '9999-12-31'
        if end < when.isoformat(): fail('Assignment end precedes start.')
        p['_ends_assignment_ids'] = []
        for a in bank_state['assignments']:
            if (a['truck_id'] == p['truck_id'] or a['trailer_id'] == p['trailer_id']) and a['start'] <= end and (a.get('end') or '9999-12-31') >= when.isoformat():
                if a['start'] >= when.isoformat(): fail('Assignment overlaps a current or later effective assignment.')
                p['_ends_assignment_ids'].append(a['id'])
    elif k == 'asset_plan':
        if p['planned_sale'] < p['acquired']: fail('Planned sale must follow acquisition.')
        if p['payoff_confirmed'] and not p.get('payoff_evidence_id'): fail('Actual payoff confirmation requires supporting evidence.')
    elif k == 'disposal':
        plan = s['plans'].get(p['asset_id'])
        if not plan or p['asset_id'] in s['disposals']: fail('A disposal requires one unsold asset with a confirmed acquisition plan.')
        cost, depreciation = D(plan['acquisition_cost']), D(p['book_accumulated_depreciation'])
        if depreciation > cost: fail('Book depreciation cannot exceed acquisition cost.')
        asset_rows = ledger_report(db, tenant, date.min, when)['general_ledger']
        book_cost = sum((D(l['debit']) - D(l['credit']) for l in asset_rows if l['asset_id'] == p['asset_id'] and l['account'] == 'equipment'), ZERO)
        book_depreciation = sum((D(l['credit']) - D(l['debit']) for l in asset_rows if l['asset_id'] == p['asset_id'] and l['account'] == 'accumulated_depreciation'), ZERO)
        if book_cost != cost or book_depreciation != depreciation:
            fail('Reconcile this asset’s acquisition and accumulated depreciation to the ledger before recording its sale.')
        # Proceeds are receivable until matched; debt payoff is a separate financing payment.
        net = D(p['gross_sale']) - D(p['selling_costs'])
        lines = [line('receivable', net, p['asset_id']), line('accumulated_depreciation', depreciation, p['asset_id']), line('equipment', -cost, p['asset_id']), line('disposal_gain', -(net - cost + depreciation), p['asset_id'])]
    elif k == 'financing':
        if D(p['business_amount']) > D(p['amount']): fail('Business portion exceeds the total.')
        if D(p['annual_rate']) > 100: fail('Annual rate is a percentage between 0 and 100.')
        if D(p['business_amount']) > 0:
            claim = resource(db, tenant, p.get('owner_claim_id'), {'owner_advance', 'bill', 'payment'})
            if claim.id not in s['claims']: fail('Financing claim is not effective yet.')
            if p.get('asset_id') != s['claims'][claim.id].get('asset_id'): fail('Financing use must match the underlying claim asset.')
            if D(p['business_amount']) > D(s['claims'][claim.id]['amount']): fail('Business allocation exceeds the original claim.')
        if p['action'] == 'commitment' and not p.get('due'): fail('Committed payments require an explicit due date.')
        if p['action'] == 'principal_payment' and p.get('payment_id'):
            payment = resource(db, tenant, p['payment_id'], {'payment'})
            if payment.payload['claim_id'] != p.get('owner_claim_id'): fail('Payment must discharge the same underlying owner claim.')
        # Supporting schedule only: never creates a second claim or expenses principal.
    elif k == 'settlement':
        if any(e.kind == k and e.payload['source_ref'] == p['source_ref'] for e in all_events): fail('Settlement source already posted. Reverse and use a new revision reference.', 'DUPLICATE_SOURCE')
        if p['period_end'] < p['period_start']: fail('Settlement period is reversed.')
        expected = D(p['freight_gross']) - D(p['carrier_retention']) - sum((D(v) for v in p['deductions'].values()), ZERO) + D(p['cash_adjustments'])
        if expected != D(p['reported_payout']): fail('Freight less carrier and deductions plus cash adjustments must equal the reported payout.', 'SETTLEMENT_UNBALANCED')
        if D(p['cash_adjustments']): fail('Non-operating cash adjustments require separately classified journal evidence before settlement posting.', 'REVIEW_REQUIRED')
        if p['loads'] and sum((D(l['freight_gross']) for l in p['loads']), ZERO) != D(p['freight_gross']): fail('Load gross does not reconcile to settlement gross.')
        asset = p['asset_id']
        lines = [line('receivable', p['reported_payout'], asset), line('freight', -D(p['freight_gross']), asset), line('carrier', p['carrier_retention'], asset)]
        for category, amount in p['deductions'].items():
            account = EXPENSE_MAP.get(category, category)
            if account not in ACCOUNTS or ACCOUNTS[account] != 'expense': fail(f'Approve a supported expense mapping for {category}.', 'REVIEW_REQUIRED')
            lines.append(line(account, amount, asset))
    elif k == 'travel':
        if p['end'] < p['start']: fail('Travel interval is reversed.')
        if p['consumption_supported'] and (p['basis'] == 'estimated' or not p.get('consumed_gallons') or D(p['consumed_gallons']) <= 0): fail('Measured MPG needs independent distance and supported consumed gallons.')
        if any(e.kind == k and e.payload['asset_id'] == p['asset_id'] and e.payload['start'] <= p['end'] and e.payload['end'] >= p['start'] for e in all_events): fail('Travel intervals overlap; use non-overlapping evidence intervals.')
    elif k == 'completed_load':
        if any(e.kind == k and e.payload['load_id'] == p['load_id'] for e in all_events): fail('Completed load already recorded.', 'DUPLICATE_SOURCE')
    elif k == 'journal':
        if not (s['policy'] or {}).get('approved'): fail('Approve the accounting policy before manual posting.')
        lines = [{**l, 'debit': D(l['debit']), 'credit': D(l['credit'])} for l in p['lines']]
        for l in lines:
            if l.get('asset_id') and not db.query(Truck).filter_by(id=l['asset_id'], tenant_id=tenant).first(): fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
        if any(l['account'] == 'cash' and (D(l['debit']) or D(l['credit'])) for l in lines) and p['cash_flow_classification'] == 'noncash': fail('Choose a cash-flow classification for a journal that changes cash.')
        description = p['description']
    elif k == 'reversal':
        original = db.query(FinancePosting).filter_by(id=p['posting_id'], tenant_id=tenant).first()
        if not original: fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
        if db.query(FinancePosting).filter_by(reversal_of=original.id).first(): fail('Posting already reversed.')
        origin = resource(db, tenant, original.event_id)
        if when < original.entry_date: fail('Reversal cannot precede the original posting.')
        if origin.kind in ('bill', 'owner_advance') and any(e.kind == 'payment' and e.payload['claim_id'] == origin.id for e in s['events'] if e.id in s['active_event_ids']):
            fail('Reverse dependent payments before reversing this obligation.')
        if origin.kind == 'settlement' and any(e.kind == 'bank_match' and e.payload.get('target_id') == origin.id and e.payload['transaction_id'] in s['matches'] for e in s['events']):
            fail('Reverse dependent deposit matches before reversing the settlement.')
        if origin.kind == 'payment' and origin.id in s['claims'] and s['claims'][origin.id]['remaining'] != D(origin.payload['amount']):
            fail('Reverse dependent owner reimbursements first.')
        if origin.kind not in ('journal', 'bill', 'owner_advance', 'payment', 'bank_match', 'settlement'):
            fail('This source needs an operational amendment before reversal.', 'REVIEW_REQUIRED')
        lines = [{'account': l.account, 'debit': l.credit, 'credit': l.debit, 'asset_id': l.asset_id} for l in db.query(FinanceLine).filter_by(posting_id=original.id)]
        reversal_of = original.id
        description = p['reason']
    elif k == 'activate_finance':
        snapshot = db.query(FinanceReport).filter_by(id=p['report_id'], tenant_id=tenant).first()
        if not snapshot: fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
        if not p['browser_acceptance_confirmed'] or snapshot.result['readiness']['status'] != 'pass': fail('Reconciliation and browser acceptance are required before switching Home.', 'CUTOVER_BLOCKED')
        if snapshot.result.get('source_sequence') != max((e.sequence for e in all_events), default=0): fail('Records changed after this report. Refresh and reconcile before switching Home.', 'STALE_REPORT')
    elif k in ('close_period', 'reopen_period'):
        if p['end'] < p['start']: fail('Period end precedes start.')
        if k == 'close_period':
            checks = readiness(db, tenant, date.fromisoformat(p['end']))
            if checks['status'] != 'pass': fail('Resolve readiness checks before closing.', 'PACKAGE_BLOCKED')
        elif not closed.get((p['start'], p['end'])): fail('Only a closed period can be reopened.')
    event = FinanceEvent(tenant_id=tenant, key=key, digest=hash_value, kind=k, effective_date=when, payload=p)
    db.add(event)
    db.flush()
    post(db, tenant, event, description, lines, reversal_of)
    return event


def ledger_report(db, tenant, start, end):
    rows = db.query(FinanceLine, FinancePosting).join(FinancePosting, FinanceLine.posting_id == FinancePosting.id).filter(FinancePosting.tenant_id == tenant, FinancePosting.entry_date <= end).order_by(FinancePosting.entry_date, FinancePosting.id, FinanceLine.id).all()
    balances, period = defaultdict(lambda: ZERO), defaultdict(lambda: ZERO)
    general, asset_income = [], defaultdict(lambda: ZERO)
    cashflows = defaultdict(lambda: ZERO)
    for l, p in rows:
        value = D(l.debit) - D(l.credit)
        balances[l.account] += value
        if start <= p.entry_date <= end:
            period[l.account] += value
            general.append({'posting_id': p.id, 'event_id': p.event_id, 'date': p.entry_date.isoformat(), 'description': p.description, 'account': l.account, 'asset_id': l.asset_id, 'debit': money(l.debit), 'credit': money(l.credit), 'reversal_of': p.reversal_of})
            if ACCOUNTS[l.account] in ('revenue', 'expense'):
                asset_income[l.asset_id] -= value
            if l.account == 'cash':
                source = resource(db, tenant, p.event_id)
                action = source.payload.get('match_type')
                if source.kind == 'reversal':
                    original = db.query(FinancePosting).filter_by(id=source.payload['posting_id'], tenant_id=tenant).one()
                    source = resource(db, tenant, original.event_id)
                    action = source.payload.get('match_type')
                bucket = 'financing' if action in ('owner_contribution', 'owner_distribution') else ('investing' if action == 'asset_sale' else 'operating')
                if source.kind == 'payment':
                    claim = resource(db, tenant, source.payload['claim_id'])
                    if claim.payload.get('category') == 'equipment': bucket = 'investing'
                    elif claim.kind == 'owner_advance': bucket = 'financing'
                if source.kind == 'journal': bucket = source.payload.get('cash_flow_classification', 'unclassified')
                if action == 'card_repayment':
                    allocated = sum((D(source.payload.get(f'{b}_amount', 0)) for b in ('operating', 'investing', 'financing')), ZERO)
                    if allocated != abs(value):
                        cashflows['unclassified'] += value
                    else:
                        for b in ('operating', 'investing', 'financing'):
                            cashflows[b] += D(source.payload.get(f'{b}_amount', 0)) * (1 if value > 0 else -1)
                else:
                    cashflows[bucket] += value
    revenue = -sum((v for a, v in period.items() if ACCOUNTS[a] == 'revenue'), ZERO)
    expenses = sum((v for a, v in period.items() if ACCOUNTS[a] == 'expense'), ZERO)
    assets = sum((v for a, v in balances.items() if ACCOUNTS[a] in ('asset', 'contra_asset')), ZERO)
    liabilities = -sum((v for a, v in balances.items() if ACCOUNTS[a] == 'liability'), ZERO)
    equity = -sum((v for a, v in balances.items() if ACCOUNTS[a] in ('equity', 'contra_equity', 'revenue', 'expense')), ZERO)
    return {
        'trial_balance': [{'account': a, 'type': ACCOUNTS[a], 'debit': money(max(v, ZERO)), 'credit': money(max(-v, ZERO))} for a, v in sorted(balances.items())],
        'general_ledger': general,
        'income_statement': {'revenue': money(revenue), 'expenses': money(expenses), 'operating_earnings': money(revenue - expenses + period['interest'] + period['depreciation'] + period['disposal_gain']), 'disposal_gain': money(-period['disposal_gain']), 'interest': money(period['interest']), 'depreciation': money(period['depreciation']), 'net_income': money(revenue - expenses), 'by_account': {a: money(-v if ACCOUNTS[a] == 'revenue' else v) for a, v in period.items() if ACCOUNTS[a] in ('revenue', 'expense')}},
        'balance_sheet': {'assets': money(assets), 'liabilities': money(liabilities), 'equity_including_earnings': money(equity), 'difference': money(assets - liabilities - equity)},
        'cash_flow': {**{a: money(cashflows[a]) for a in ('operating', 'investing', 'financing', 'unclassified')}, 'opening_balance': money(balances['cash'] - period['cash'] + cashflows['opening']), 'net_change': money(sum((v for a, v in cashflows.items() if a != 'opening'), ZERO)), 'closing_balance': money(balances['cash'])},
        'asset_earnings': [{'asset_id': aid, 'earnings': money(value)} for aid, value in asset_income.items()],
        'ledger_cash': money(balances['cash']), 'ledger_cards': money(-balances['card_payable']), 'ledger_payable': money(-balances['payable']), 'ledger_owner_claims': money(-balances['owner_advance']),
    }


def readiness(db, tenant, as_of):
    s = state(db, tenant, as_of)
    policy = s['policy'] or {}
    checks = []
    for key, title in [('approved', 'Accounting policy'), ('opening_confirmed', 'Opening balances'), ('account_coverage_confirmed', 'Account coverage'), ('history_confirmed', 'Historical source coverage'), ('carrier_presentation_confirmed', 'Carrier gross/net policy'), ('owner_treatment_confirmed', 'Owner and mixed-use financing policy'), ('depreciation_confirmed', 'Book depreciation'), ('tax_basis_confirmed', 'Prior tax basis and elections')]:
        checks.append({'code': key, 'label': title, 'status': 'pass' if policy.get(key) else 'unknown'})
    cash = cash_position(db, tenant, as_of)
    checks.append({'code': 'cash_reconciliation', 'label': 'Cash and card statement coverage', 'status': 'pass' if cash['status'] == 'reconciled' else 'unknown'})
    unmatched = [t for t in s['transactions'] if t not in s['matches']]
    checks.append({'code': 'unmatched_transactions', 'label': f'{len(unmatched)} unmatched transactions', 'status': 'block' if unmatched else 'pass'})
    ledger = ledger_report(db, tenant, date.min, as_of)
    reconciled = cash['business_cash'] is not None and D(cash['business_cash']) == D(ledger['ledger_cash']) and D(cash['card_obligations']) == max(D(ledger['ledger_cards']), ZERO)
    checks.append({'code': 'ledger_to_bank', 'label': 'Ledger agrees with bank and card balances', 'status': 'pass' if reconciled else 'block'})
    claims_match = sum((c['remaining'] for c in s['claims'].values() if c['creditor'] == 'vendor'), ZERO) == D(ledger['ledger_payable']) and sum((c['remaining'] for c in s['claims'].values() if c['creditor'] == 'owner'), ZERO) == D(ledger['ledger_owner_claims'])
    checks.append({'code': 'cash_flow_classification', 'label': 'Cash-flow classifications reviewed', 'status': 'pass' if D(ledger['cash_flow']['unclassified']) == 0 else 'block'})
    checks.append({'code': 'claims_to_ledger', 'label': 'Bills and owner claims agree with ledger', 'status': 'pass' if claims_match else 'block'})
    checks.append({'code': 'balanced_ledger', 'label': 'Balanced trial balance', 'status': 'pass' if D(ledger['balance_sheet']['difference']) == 0 else 'block'})
    return {'status': 'block' if any(c['status'] == 'block' for c in checks) else ('unknown' if any(c['status'] == 'unknown' for c in checks) else 'pass'), 'checks': checks}


def capital_schedule(db, tenant, as_of):
    s = state(db, tenant, as_of)
    results = []
    ledger = ledger_report(db, tenant, date.min, as_of)
    for aid, plan in s['plans'].items():
        cost = D(plan['acquisition_cost'])
        resale = max(D(plan['expected_resale']) - D(plan['selling_costs']), ZERO)
        target = max(cost - resale, ZERO)
        funded = sum((r['balance'] for r in s['reserves'].values() if r['purpose'] == 'capital' and r.get('asset_id') == aid), ZERO)
        remaining = max(target - funded, ZERO)
        days = max((date.fromisoformat(plan['planned_sale']) - as_of).days, 0)
        sale = s['disposals'].get(aid)
        # Lifetime earnings excludes book depreciation and disposal gain before acquisition/net sale bridge.
        earnings = ZERO
        for row in ledger['general_ledger']:
            if row['asset_id'] == aid and ACCOUNTS[row['account']] in ('revenue', 'expense') and row['account'] not in ('depreciation', 'disposal_gain'):
                earnings += D(row['credit']) - D(row['debit'])
        results.append({**plan, 'target': money(target), 'funded': money(funded), 'shortfall': money(remaining), 'remaining_days': days, 'required_weekly': money(remaining * 7 / days) if days else None, 'overdue': days == 0 and remaining > 0, 'realized_lifetime_profit': money(earnings - cost + D(sale['gross_sale']) - D(sale['selling_costs'])) if sale else None, 'sale_cash_after_financing': money(D(sale['gross_sale']) - D(sale['selling_costs']) - D(sale['financing_payoff'])) if sale else None, 'evidence_status': 'provisional' if not (s['policy'] or {}).get('history_confirmed') else 'confirmed'})
    return results


def fuel_performance(db, tenant, as_of):
    s = state(db, tenant, as_of)
    since = as_of - timedelta(days=27)
    rows = []
    for truck in db.query(Truck).filter_by(tenant_id=tenant, vehicle_type='truck').all():
        travel = [e.payload for e in s['events'] if e.kind == 'travel' and e.payload['asset_id'] == truck.id and e.payload['basis'] != 'estimated' and since.isoformat() <= e.payload['start'] and e.payload['end'] <= as_of.isoformat()]
        miles = sum((D(t['miles']) for t in travel), ZERO)
        # Only complete independent intervals support consumption. Purchases are different evidence.
        measured = [t for t in travel if t['consumption_supported'] and t.get('consumed_gallons')]
        mpg = sum((D(t['miles']) for t in measured), ZERO) / sum((D(t['consumed_gallons']) for t in measured), ZERO) if measured else None
        fuels = [f for x in s['settlements'] if x['asset_id'] == truck.id for f in x['fuel'] if since.isoformat() <= f['date'] <= as_of.isoformat() and f['product'] == 'diesel' and f.get('gallons')]
        gallons = sum((D(f['gallons']) for f in fuels), ZERO)
        covered_days = set()
        for t in travel:
            day = date.fromisoformat(t['start'])
            while day <= date.fromisoformat(t['end']):
                covered_days.add(day)
                day += timedelta(days=1)
        complete_window = len(covered_days) == 28
        baselines = [D(t['baseline_mpg']) for t in travel if t.get('baseline_mpg') and D(t['baseline_mpg']) > 0]
        baseline = baselines[-1] if baselines else None
        alerts = []
        if mpg and (mpg < 6 or mpg > 7): alerts.append('Measured MPG outside your 6–7 reference band; review conditions and evidence.')
        if mpg and baseline and mpg < baseline * D('.9'): alerts.append('Measured MPG is more than 10% below this truck’s recorded baseline.')
        rows.append({'asset_id': truck.id, 'name': truck.name, 'start': since.isoformat(), 'end': as_of.isoformat(), 'measured_mpg': money(mpg) if mpg else None, 'miles_per_gallon_purchased': money(miles / gallons) if gallons and complete_window else None, 'independent_miles': money(miles), 'diesel_gallons_purchased': money(gallons), 'window_complete': complete_window, 'alerts': alerts, 'note': 'Fuel purchases can fall in a different period from consumption. Estimated miles and unknown products are excluded.'})
    return rows


def legacy_comparison(db, tenant, start, end):
    from app.models.settlement import Settlement
    records = db.query(Settlement).join(Truck, Settlement.truck_id == Truck.id).filter(Truck.tenant_id == tenant, Settlement.settlement_date >= start, Settlement.settlement_date <= end, Settlement.source_settlement_id.is_(None)).all()
    rows = []
    for x in records:
        overview = x.overview_amounts or {}
        allocations = D(x.trailer_income_split_amount) + D(x.repair_reserve_amount)
        after_carrier = D(x.gross_revenue) + allocations
        gross = D(overview['gross_before_dispatch']) if overview.get('gross_before_dispatch') is not None else after_carrier
        retention = gross - after_carrier
        categories = {k: money(v) for k, v in (x.expense_categories or {}).items()}
        # Aggregate expense is preserved when categories are incomplete; discrepancy is visible.
        expense = D(x.expenses)
        modeled_interest = D(categories.get('loan_interest', 0))
        settlement_remainder = after_carrier - expense + modeled_interest
        rows.append({'legacy_id': x.id, 'asset_id': x.truck_id, 'name': x.truck.name, 'trailer_id': x.trailer_income_split_trailer_id, 'date': x.settlement_date.isoformat(), 'period_start': x.week_start.isoformat() if x.week_start else None, 'period_end': x.week_end.isoformat() if x.week_end else None, 'freight_gross': money(gross), 'carrier_retention': money(retention), 'deductions': categories, 'operating_deductions': money(expense - modeled_interest), 'settlement_remainder': money(settlement_remainder), 'legacy_net': money(x.net_profit), 'internal_allocations': money(allocations), 'modeled_interest_excluded': money(modeled_interest), 'difference': money(settlement_remainder - D(x.net_profit)), 'category_difference': money(expense - sum((D(v) for v in categories.values()), ZERO)), 'source_url': x.pdf_file_path, 'evidence_status': 'legacy_unverified', 'miles': money(x.miles_driven) if x.miles_driven is not None else None, 'mileage_basis': 'unknown'})
    return {'rows': rows, 'totals': {key: money(sum((D(r[key]) for r in rows), ZERO)) for key in ('freight_gross', 'carrier_retention', 'operating_deductions', 'settlement_remainder', 'legacy_net', 'difference')}, 'note': 'Read-only comparison. Internal allocations are added back; modeled interest is excluded. Source evidence must be verified before posting. No records have been migrated.'}


def report(db, tenant, start, end, as_of):
    s = state(db, tenant, as_of)
    ledger = ledger_report(db, tenant, start, end)
    days = (end - start).days + 1
    settled = [x for x in s['settlements'] if start.isoformat() <= x['date'] <= end.isoformat()]
    gross = D(ledger['income_statement']['by_account'].get('freight', 0))
    by_category = defaultdict(lambda: ZERO)
    for x in settled:
        by_category['carrier'] += D(x['carrier_retention'])
        for a, v in x['deductions'].items(): by_category[EXPENSE_MAP.get(a, a)] += D(v)
    breakdown = [{'category': a, 'amount': money(v), 'percent_of_freight': money(v / gross * 100) if gross else None} for a, v in by_category.items()]
    pairs = []
    for truck in db.query(Truck).filter_by(tenant_id=tenant, vehicle_type='truck').all():
        truck_rows = [x for x in settled if x['asset_id'] == truck.id]
        trailer_ids = sorted({x['trailer_id'] for x in truck_rows if x.get('trailer_id')})
        trailer_ids = sorted(set(trailer_ids) | {a['trailer_id'] for a in s['assignments'] if a['truck_id'] == truck.id and a['start'] <= end.isoformat() and (a.get('end') or '9999-12-31') >= start.isoformat()})
        assets = [truck.id, *trailer_ids]
        pair_earnings = ZERO
        components = defaultdict(lambda: ZERO)
        for l in ledger['general_ledger']:
            if l['asset_id'] == truck.id or (l['asset_id'] in trailer_ids and any(a['truck_id'] == truck.id and a['trailer_id'] == l['asset_id'] and a['start'] <= l['date'] <= (a.get('end') or '9999-12-31') for a in s['assignments'])):
                if ACCOUNTS[l['account']] in ('expense', 'revenue'):
                    contribution = D(l['credit']) - D(l['debit'])
                    pair_earnings += contribution
                    components[l['asset_id']] += contribution
        pairs.append({'truck_id': truck.id, 'name': truck.name, 'trailer_ids': trailer_ids, 'freight_gross': money(sum((D(x['freight_gross']) for x in truck_rows), ZERO)), 'earnings': money(pair_earnings), 'per_calendar_day': money(pair_earnings / days), 'settlements': truck_rows, 'asset_ids': assets, 'components': [{'asset_id': aid, 'earnings': money(value)} for aid, value in components.items()]})
    exceptions = [{'code': c['code'], 'message': c['label'], 'status': c['status'], 'href': '/finance/accounting'} for c in readiness(db, tenant, as_of)['checks'] if c['status'] != 'pass']
    for t in s['transactions'].values():
        if t['id'] not in s['matches']: exceptions.append({'code': 'unmatched_transaction', 'message': f"{t['date']} · {t['description']} · ${t['amount']}", 'status': 'block', 'href': '/finance/money', 'transaction_id': t['id']})
    paid_loads = {l['load_id'] for x in s['settlements'] for l in x['loads']}
    for e in s['events']:
        if e.kind == 'completed_load' and e.payload['load_id'] not in paid_loads and (as_of - e.effective_date).days >= 2 * e.payload['settlement_cycle_days']:
            exceptions.append({'code': 'unmatched_load', 'message': f"Completed load {e.payload['load_id']} has no matched settlement after two cycles.", 'status': 'block', 'href': '/finance/settlements'})
    fuel = fuel_performance(db, tenant, as_of)
    for f in fuel:
        for alert in f['alerts']: exceptions.append({'code': 'fuel_review', 'message': f"{f['name']}: {alert}", 'status': 'unknown', 'href': '/finance/connections'})
    trend = defaultdict(lambda: {'freight': ZERO, 'earnings': ZERO})
    for l in ledger['general_ledger']:
        amount = D(l['credit']) - D(l['debit'])
        if l['account'] == 'freight': trend[l['date']]['freight'] += amount
        if ACCOUNTS[l['account']] in ('revenue', 'expense'): trend[l['date']]['earnings'] += amount
    overhead = sum((D(x['earnings']) for x in ledger['asset_earnings'] if x['asset_id'] is None), ZERO)
    source_events = [{'id': e.id, 'kind': e.kind, 'effective_date': e.effective_date.isoformat(), 'payload': e.payload} for e in s['events']]
    evidence_ids = {eid for e in s['events'] for eid in [e.payload.get('evidence_id'), e.payload.get('payoff_evidence_id'), *e.payload.get('evidence_ids', [])] if eid}
    manifest = [{'id': e.id, 'filename': e.filename, 'sha256': e.sha256, 'source_key': e.source_key, 'supersedes_id': e.supersedes_id, 'extraction_version': e.extraction_version} for e in db.query(FinanceEvidence).filter(FinanceEvidence.tenant_id == tenant, FinanceEvidence.id.in_(evidence_ids)).all()]
    result = {'tenant_id': tenant, 'currency': 'USD', 'basis': 'accrual', 'source_events': source_events, 'evidence_manifest': manifest, 'period': {'start': start.isoformat(), 'end': end.isoformat(), 'calendar_days': days}, 'as_of': as_of.isoformat(), 'source_cutoff': max((e.created_at.isoformat() for e in s['events']), default=None), 'source_sequence': max((e.sequence for e in s['events']), default=0), 'readiness': readiness(db, tenant, as_of), 'owner_cash': cash_position(db, tenant, as_of), 'ledger': ledger, 'revenue_breakdown': {'freight_gross': money(gross), 'rows': breakdown, 'settlement_remainder': money(sum((D(x['reported_payout']) for x in settled), ZERO))}, 'pairs': pairs, 'shared_company_result': money(overhead), 'unassigned_asset_result': money(D(ledger['income_statement']['net_income']) - overhead - sum((D(p['earnings']) for p in pairs), ZERO)), 'capital': capital_schedule(db, tenant, as_of), 'fuel': fuel, 'exceptions': exceptions, 'trend': [{'date': d, **{k: money(v) for k, v in vals.items()}} for d, vals in sorted(trend.items())], 'legacy_comparison': legacy_comparison(db, tenant, start, end), 'label': 'Draft — source and opening evidence required' if readiness(db, tenant, as_of)['status'] != 'pass' else 'Reconciled management report'}

    from app.services.fleet_insights import owner_insights
    result['owner_insights'] = owner_insights(result)
    from app.services.retention import retention_report
    result['retention'] = retention_report(db, tenant, result)
    return result


def auto_reconcile(db, tenant):
    """Only exact, unique references and amounts under an approved import policy."""
    import re
    from app.schemas.finance import Command
    s = state(db, tenant, date.max)
    if not (s['policy'] or {}).get('approved'): return []
    approved_accounts = set()
    for st in s['statements'].values():
        mapping = resource(db, tenant, st['mapping_id'], {'csv_mapping'})
        if mapping.payload.get('approved_for_matching'): approved_accounts.add(st['account_id'])
    matched = []
    for t in s['transactions'].values():
        if t['id'] in s['matches'] or s['allocated'].get(t['id']) or t['account_id'] not in approved_accounts: continue
        candidates = []
        amount = D(t['amount'])
        for c in (s['settlements'] if amount > 0 else s['claims'].values()):
            ref = c.get('source_ref', '')
            if len(ref) < 4 or not re.search(r'(?<!\w)' + re.escape(ref) + r'(?!\w)', t['description'], re.I): continue
            source = resource(db, tenant, c['id'])
            if source.effective_date.isoformat() > t['date']: continue
            if amount > 0:
                already = sum((D(s['transactions'][e.payload['transaction_id']]['amount']) for e in s['events'] if e.kind == 'bank_match' and e.payload.get('target_id') == c['id'] and e.payload['transaction_id'] in s['matches']), ZERO)
                if D(c['reported_payout']) - already == amount: candidates.append({'kind': 'bank_match', 'transaction_id': t['id'], 'target_id': c['id'], 'match_type': 'settlement'})
            elif c['remaining'] == -amount and c['creditor'] == 'vendor':
                candidates.append({'kind': 'payment', 'claim_id': c['id'], 'transaction_id': t['id'], 'amount': money(-amount), 'payer': 'card' if s['accounts'][t['account_id']]['account_type'] == 'card' else 'business'})
        if len(candidates) == 1:
            try:
                with db.begin_nested():
                    event = append_command(db, tenant, Command(effective_date=t['date'], payload=candidates[0]), 'auto:' + digest(candidates[0]))
                matched.append(event.id)
            except HTTPException:
                # Closed period, stale candidate or ambiguous subledger remains in review queue.
                continue
    return matched
