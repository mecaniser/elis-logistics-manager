"""Repair evidence and explicitly linked obligations, without inferred payments."""
from collections import Counter
from app.services.repair_payee import payee_details
from app.models.repair import Repair
from app.models.truck import Truck
from app.models.finance import FinanceEvidence
from app.services import finance as f


def repair_history(db, tenant, as_of):
    records = db.query(Repair, Truck).join(Truck, Repair.truck_id == Truck.id).filter(Truck.tenant_id == tenant).order_by(Repair.id).all()
    docs = db.query(FinanceEvidence).filter_by(tenant_id=tenant).all()
    superseded = {d.supersedes_id for d in docs if d.supersedes_id}
    confirmations = {d.extracted['repair_id']: d for d in docs if d.id not in superseded and d.extraction_version == 'owner-confirmation-v1'}
    by_repair = {}
    for d in docs:
        if d.id in superseded: continue
        for rid in d.extracted.get('legacy_repair_ids', []):
            by_repair.setdefault(rid, []).append(d)
    state = f.state(db, tenant, as_of)
    rows = []
    evidence_by_row = {}
    for repair, asset in records:
        if repair.repair_date and repair.repair_date > as_of: continue
        evidence = by_repair.get(repair.id, [])
        evidence_by_row[repair.id] = evidence
        events = [e for e in state['events'] if e.kind in ('bill', 'owner_advance') and e.payload.get('legacy_repair_id') == repair.id]
        active = [e for e in events if e.id in state['active_event_ids']]
        claims = [c for c in state['claims'].values() if c.get('legacy_repair_id') == repair.id]
        payments = [e for e in state['events'] if e.kind == 'payment' and e.id in state['active_event_ids'] and e.payload['claim_id'] in {c['id'] for c in claims}]
        vendor = sum((c['remaining'] for c in claims if c['creditor'] == 'vendor'), f.ZERO)
        owner = sum((c['remaining'] for c in claims if c['creditor'] == 'owner'), f.ZERO)
        issues = []
        if not evidence: issues.append('missing_preserved_evidence')
        if not repair.repair_date: issues.append('incurred_date_required')
        if repair.cost is None or repair.cost <= 0: issues.append('incurred_amount_required')
        text = ' '.join(str(x or '') for x in (repair.title, repair.details, repair.description)).lower()
        if any(t in text for t in ('not charged', 'complimentary', 'settlement deduct', 'recovery', 'reimbursement')) or (repair.cost is not None and 0 < repair.cost <= 0.10):
            issues.append('cost_or_recovery_treatment_review')
        if repair.paid_from_reserve: issues.append('legacy_reserve_flag_needs_funding_evidence')
        if not active: issues.append('obligation_not_linked')
        if not payments: issues.append('payment_evidence_not_linked')
        totals = []
        for d in evidence:
            review = d.extracted.get('invoice_review') or {}
            if review.get('source_total') is not None:
                totals.append(review['source_total'])
                if repair.cost is not None and f.D(review['source_total']) != repair.cost: issues.append('invoice_amount_difference')
        if len(set(totals)) > 1: issues.append('conflicting_invoice_totals')
        rows.append({'legacy_id': repair.id, 'asset_id': asset.id, 'asset_name': asset.name,
                     'date': repair.repair_date.isoformat() if repair.repair_date else None,
                     'description': repair.title or repair.description, 'invoice_number': repair.invoice_number,
                     'recorded_cost': f.money(repair.cost) if repair.cost is not None else None,
                     'source_totals': sorted(set(totals)),
                     'evidence': [{'id': d.id, 'sha256': d.sha256, 'media_type': d.media_type, 'extraction_version': d.extraction_version} for d in sorted(evidence, key=lambda d: d.id)],
                     'obligation_event_ids': [e.id for e in events], 'payment_event_ids': [e.id for e in payments],
                     'recorded_vendor_outstanding': f.money(vendor) if active else None,
                     'recorded_owner_reimbursement': f.money(owner) if active else None,
                     'payment_status': 'linked_activity' if payments else 'unverified',
                     'issues': list(dict.fromkeys(issues)), 'automatic_posting_allowed': False})
    for row in rows:
        row['review_snapshot'] = f.digest({k: row[k] for k in ('legacy_id', 'asset_id', 'date', 'description', 'invoice_number', 'recorded_cost', 'source_totals', 'evidence')})
        confirmation = confirmations.get(row['legacy_id'])
        row['confirmation'] = ({'id': confirmation.id, **confirmation.extracted,
                                'stale': confirmation.extracted.get('snapshot') != row['review_snapshot']} if confirmation else None)
        row['payee'] = payee_details(evidence_by_row[row['legacy_id']])
        if row['confirmation'] and not row['confirmation']['stale'] and row['confirmation'].get('payee'):
            row['payee'] = {**row['payee'], 'name': row['confirmation']['payee'], 'basis': 'owner_confirmation'}
        row['batch_eligible'] = bool(row['source_totals']) and not confirmation and not row['obligation_event_ids'] and not any(i in row['issues'] for i in (
            'invoice_amount_difference', 'conflicting_invoice_totals', 'incurred_date_required',
            'incurred_amount_required', 'cost_or_recovery_treatment_review'))
    return {'version': 'repair-history-v1', 'tenant_id': tenant, 'as_of': as_of.isoformat(),
            'scope': 'legacy_repairs', 'basis': 'evidence_and_explicit_ledger_links',
            'evidence_status': 'review_required', 'rows': rows,
            'coverage': {'records': len(rows), 'with_preserved_evidence': sum(bool(r['evidence']) for r in rows),
                         'with_linked_payments': sum(bool(r['payment_event_ids']) for r in rows),
                         'issue_counts': dict(Counter(i for r in rows for i in r['issues']))},
            'limitations': ['Invoice totals are not proof of payment or current unpaid balances.',
                           'Legacy reserve flags and nominal costs do not establish funded reserves or new expenses.',
                           'Linked card charges do not establish bank repayment of card principal.',
                           'Settlements, recoveries and personally paid costs require explicit links to avoid duplication.']}
