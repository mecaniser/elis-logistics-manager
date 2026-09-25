"""Turn explicit unreimbursed personal payments into linked accrual entries once."""
import base64
import json
from datetime import date
from fastapi import HTTPException
from app.models.finance import FinanceEvidence
from app.schemas.finance import Command
from app.services import finance as f

VERSION = 'repair-owner-posting-v1'


def assessment(db, tenant, row, ledger_state=None, posting_links=None):
    c = row.get('confirmation')
    result = {'repair_id': row['legacy_id'], 'status': 'not_applicable', 'reason': '', 'owner_claim_id': None}
    if not c: return result
    links = posting_links if posting_links is not None else db.query(FinanceEvidence).filter_by(tenant_id=tenant, extraction_version=VERSION, source_key=f"repair-owner-posting:{row['legacy_id']}").all()
    fingerprint = f.digest({'asset': row['asset_id'], 'incurred': row['date'], 'cost': row['recorded_cost'],
                            'paid': c['paid_amount'], 'paid_date': c['paid_date'], 'source': c['source'],
                            'status': c['status'], 'reimbursement': c.get('reimbursement', 'unknown')})
    result['fingerprint'] = fingerprint
    def review(reason): return {**result, 'status': 'review_required', 'reason': reason}
    if links:
        linked = links[0].extracted
        s = ledger_state if ledger_state is not None else f.state(db, tenant, date.today())
        if c['stale'] or linked['fingerprint'] != fingerprint:
            return review('Payment facts changed after posting. Review the existing entry before adjusting it.')
        if linked['bill_id'] not in s['active_event_ids'] or linked['payment_id'] not in s['active_event_ids']:
            return review('An entry was reversed. Review the correction before posting again.')
        claim = s['claims'].get(linked['payment_id'])
        return {**result, 'status': 'posted', 'owner_claim_id': linked['payment_id'], 'remaining': f.money(claim['remaining']) if claim else None,
                'reason': 'Recorded once in Accounting; reimbursements reduce the amount still owed.'}
    if c['source'] != 'personal' or c['status'] not in ('paid', 'partial'): return result
    if c['stale']: return review('Repair details changed. Review the payment confirmation.')
    if c.get('reimbursement') == 'reimbursed':
        return {**result, 'status': 'historical_reimbursed', 'remaining': '0.00',
                'reason': 'Reimbursed—confirmed by owner. Repayment date and bank transaction are not verified.'}
    if c.get('reimbursement') != 'owed': return review('Confirm how much the business still owes you before creating a reimbursement balance.')
    if not row['date'] or not c['paid_date']: return review('Confirm the invoice and payment dates.')
    if c['paid_date'] < row['date']: return review('Payment precedes the invoice. Review the advance payment treatment.')
    if row['obligation_event_ids']: return review('This repair already has an accounting obligation. Match it instead of creating another.')
    if any(i in row['issues'] for i in ('invoice_amount_difference', 'conflicting_invoice_totals', 'cost_or_recovery_treatment_review', 'incurred_amount_required')):
        return review('Resolve the invoice amount or special cost treatment first.')
    closed = {}
    for e in (ledger_state['events'] if ledger_state is not None else f.events(db, tenant)):
        if e.kind in ('close_period', 'reopen_period'): closed[(e.payload['start'], e.payload['end'])] = e.kind == 'close_period'
    if any(active and any(start <= d <= end for d in (row['date'], c['paid_date'])) for (start, end), active in closed.items()):
        return review('A required period is closed. Reopen it or record an approved dated correction.')
    return {**result, 'status': 'ready', 'reason': 'Confirmed personal payment, still owed by the business.'}


def post_owner_payment(db, tenant, row):
    result = assessment(db, tenant, row)
    if result['status'] != 'ready': return result
    c = row['confirmation']
    try:
        # Preserve the confirmation even if either accounting entry needs review.
        # Both entries and their link must succeed together.
        with db.begin_nested():
            bill = f.append_command(db, tenant, Command(effective_date=date.fromisoformat(row['date']), payload={
                'kind': 'bill', 'legacy_repair_id': row['legacy_id'], 'asset_id': row['asset_id'],
                'category': 'repairs', 'amount': row['recorded_cost'], 'description': row['description'] or 'Repair',
                'source_ref': f"repair-owner:{row['legacy_id']}", 'evidence_id': c['id']}), f"repair-owner-bill:{row['legacy_id']}")
            payment = f.append_command(db, tenant, Command(effective_date=date.fromisoformat(c['paid_date']), payload={
                'kind': 'payment', 'claim_id': bill.id, 'amount': c['paid_amount'], 'payer': 'owner', 'evidence_id': c['id']}), f"repair-owner-payment:{row['legacy_id']}")
            data = {'fingerprint': result['fingerprint'], 'confirmation_id': c['id'], 'bill_id': bill.id, 'payment_id': payment.id}
            content = json.dumps(data, sort_keys=True).encode()
            db.add(FinanceEvidence(tenant_id=tenant, sha256=f.digest(data), filename='repair-owner-posting.json', media_type='application/json',
                source_key=f"repair-owner-posting:{row['legacy_id']}", content_base64=base64.b64encode(content).decode(), extraction_version=VERSION, extracted=data))
            db.flush()
        return {**result, 'status': 'posted', 'owner_claim_id': payment.id, 'remaining': c['paid_amount'], 'reason': 'Repair expense and personal payment recorded in Accounting.'}
    except HTTPException as exc:
        detail = exc.detail
        return {**result, 'status': 'review_required', 'reason': detail.get('message', str(detail)) if isinstance(detail, dict) else str(detail)}


def process_confirmed(db, tenant, ids=None):
    from app.services.repair_history import repair_history
    f.lock_business(db, tenant)
    rows = repair_history(db, tenant, date.today())['rows']
    return [post_owner_payment(db, tenant, row) for row in rows if ids is None or row['legacy_id'] in ids]


from pydantic import BaseModel, ConfigDict, Field
from app.schemas.finance import PositiveMoney


class ReimbursementMatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transaction_id: str = Field(min_length=1, max_length=80)
    amount: PositiveMoney


def match_reimbursement(db, tenant, claim_id, request, key):
    f.lock_business(db, tenant)
    s = f.state(db, tenant, date.today())
    claim = s['claims'].get(claim_id)
    if not claim or claim['creditor'] != 'owner' or not claim.get('legacy_repair_id'):
        f.fail('Owner reimbursement not found.', 'RESOURCE_NOT_FOUND', 404)
    t = s['transactions'].get(request.transaction_id)
    if not t: f.fail('Choose a reconciled business payment.')
    account = s['accounts'][t['account_id']]
    if account['account_type'] not in ('bank', 'cash'): f.fail('Reimbursements must come from business bank or cash funds.')
    return f.append_command(db, tenant, Command(effective_date=t['date'], payload={
        'kind': 'payment', 'claim_id': claim_id, 'amount': request.amount,
        'payer': 'cash' if account['account_type'] == 'cash' else 'business', 'transaction_id': t['id']}), key)
