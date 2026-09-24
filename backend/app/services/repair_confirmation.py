"""Versioned owner confirmations; no expense, reimbursement or cash side effects."""
import base64
import hashlib
import json
from datetime import date
from app.models.finance import FinanceEvidence
from app.services import finance as f
from app.services.repair_history import repair_history


def save_confirmation(db, tenant, request):
    f.lock_business(db, tenant)
    rows = {r['legacy_id']: r for r in repair_history(db, tenant, date.today())['rows']}
    if len({i.repair_id for i in request.items}) != len(request.items):
        f.fail('Select each repair only once.')
    if request.paid_date and request.paid_date > date.today():
        f.fail('Payment date cannot be in the future.')
    if request.status in ('unknown', 'unpaid') and (request.paid_amount or request.paid_date or request.method != 'unknown' or request.source != 'unknown'):
        f.fail('Unpaid or unknown status cannot include payment details.')
    if request.status == 'partial' and (len(request.items) != 1 or not request.paid_amount):
        f.fail('Confirm partial payments one repair at a time with the total paid so far.')
    results = []
    for item in request.items:
        row = rows.get(item.repair_id)
        if not row: f.fail('Repair not found.', 'RESOURCE_NOT_FOUND', 404)
        if row['review_snapshot'] != item.snapshot:
            f.fail('Repair details changed. Refresh and review before saving.', 'STALE_REPAIR')
        if len(request.items) > 1 and not row['batch_eligible']:
            # Retry of an identical batch is still allowed below, after content matching.
            if not row['confirmation']: f.fail('This repair needs individual review.', 'REVIEW_REQUIRED')
        if request.status == 'paid' and not row['recorded_cost']:
            f.fail('Confirm the repair amount before marking it paid.')
        amount = f.D(row['recorded_cost'] or 0)
        if request.status in ('paid', 'partial') and (amount <= 0 or any(i in row['issues'] for i in ('invoice_amount_difference', 'conflicting_invoice_totals', 'cost_or_recovery_treatment_review'))):
            f.fail('Resolve the invoice amount or cost treatment using Edit before confirming payment.', 'REVIEW_REQUIRED')
        if request.status == 'partial' and request.paid_amount >= amount:
            f.fail('Partial payment must be less than the repair amount.')
        if request.status == 'paid' and request.paid_amount is not None and request.paid_amount != amount:
            f.fail('Paid in full must match the repair amount.')
        payload = {'kind': 'repair_owner_confirmation', 'repair_id': item.repair_id,
                   'snapshot': item.snapshot, 'previous_id': item.previous_id,
                   'status': request.status, 'method': request.method, 'source': request.source,
                   'paid_amount': f.money(amount) if request.status == 'paid' else f.money(request.paid_amount) if request.paid_amount else None,
                   'paid_date': request.paid_date.isoformat() if request.paid_date else None,
                   'note': request.note, 'basis': 'owner_confirmation'}
        if request.payee and request.payee.strip():
            payload['payee'] = request.payee.strip()
        content = json.dumps(payload, sort_keys=True).encode()
        digest = hashlib.sha256(content).hexdigest()
        existing = db.query(FinanceEvidence).filter_by(tenant_id=tenant, sha256=digest).first()
        if existing:
            results.append(existing.id); continue
        current = row['confirmation']
        if (current['id'] if current else None) != item.previous_id:
            f.fail('A newer confirmation exists. Refresh before changing it.', 'STALE_REVIEW')
        if len(request.items) > 1 and not row['batch_eligible']:
            f.fail('This repair needs individual review.', 'REVIEW_REQUIRED')
        evidence = FinanceEvidence(tenant_id=tenant, sha256=digest, filename=f'repair-{item.repair_id}-confirmation.json',
            media_type='application/json', content_base64=base64.b64encode(content).decode(),
            source_key=f'repair-confirmation:{item.repair_id}', supersedes_id=item.previous_id,
            extraction_version='owner-confirmation-v1', extracted=payload)
        db.add(evidence); db.flush(); results.append(evidence.id)
    return {'ids': results, 'status': 'owner_confirmed', 'posted': False}
