"""Read-only, conservative posting plan. Candidates are never posting approval."""
import base64
import hashlib
from collections import Counter
from pydantic import ValidationError
from app.models.finance import FinanceEvidence
from app.schemas.finance import Command
from app.services import finance as f
from app.services.settlement_history import settlement_history

VERSION = 'reconstruction-plan-v1'
# Operational signals are retained but do not imply that an expense is invalid.
BLOCKING = {'missing_source', 'mapping', 'payout_difference', 'load_total',
            'fuel_total', 'source_row_review', 'duplicate_source', 'repeated_load',
            'service_date', 'stored_difference', 'mileage_total'}


def reconstruction_plan(db, tenant):
    history = settlement_history(db, tenant)
    docs = {e.id: e for e in db.query(FinanceEvidence).filter_by(tenant_id=tenant).all()}
    events = f.events(db, tenant)
    posted = [e for e in events if e.kind == 'settlement']
    closed = {}
    for e in events:
        if e.kind in ('close_period', 'reopen_period'):
            closed[(e.payload['start'], e.payload['end'])] = e.kind == 'close_period'
    source_refs = Counter(r['source_ref'] for r in history['rows'] if r['source_ref'])
    children = Counter(e.supersedes_id for e in docs.values() if e.supersedes_id)
    result = []
    for row in history['rows']:
        reasons = sorted({i['code'] for i in row['issues']} & BLOCKING)
        doc = docs.get(row['evidence_id'])
        proposal = (doc.extracted.get('proposal') or {}) if doc else {}
        if doc:
            try:
                valid = hashlib.sha256(base64.b64decode(doc.content_base64, validate=True)).hexdigest() == doc.sha256
            except (ValueError, TypeError):
                valid = False
            if not valid: reasons.append('source_hash_mismatch')
            # A forked amendment chain cannot silently select a winning version.
            ancestor, seen = doc, set()
            while ancestor:
                if ancestor.id in seen:
                    reasons.append('amendment_conflict'); break
                seen.add(ancestor.id)
                if children[ancestor.id] > 1: reasons.append('amendment_conflict')
                ancestor = docs.get(ancestor.supersedes_id)
        if not proposal or not proposal.get('source_ref', '').startswith('77cargo:'):
            reasons.append('posting_mapping_required')
        if row['source_ref'] and source_refs[row['source_ref']] > 1:
            reasons.append('non_unique_source_reference')
        if any(active and start <= row['date'] <= end for (start, end), active in closed.items()):
            reasons.append('closed_period')
        if f.D(proposal.get('cash_adjustments')):
            reasons.append('cash_adjustment_classification')
        unsupported = [k for k in proposal.get('deductions', {})
                       if f.ACCOUNTS.get(f.EXPENSE_MAP.get(k, k)) != 'expense']
        if unsupported: reasons.append('expense_mapping_required')
        matching = [e for e in posted if e.payload.get('legacy_id') == row['id']
                    or (row['evidence_id'] and e.payload.get('evidence_id') == row['evidence_id'])
                    or (row['source_ref'] and e.payload.get('source_ref') == row['source_ref'])]
        command, lines = None, []
        if proposal:
            payload = {**proposal, 'evidence_id': row['evidence_id'], 'asset_id': row['asset_id'], 'legacy_id': row['id']}
            try:
                parsed = Command(effective_date=row['date'], payload=payload)
                command = parsed.model_dump(mode='json')
                if payload['period_start'] > payload['period_end']:
                    reasons.append('reversed_period')
            except ValidationError:
                reasons.append('posting_schema_required')
        if matching and command:
            for existing in matching:
                if existing.effective_date.isoformat() != row['date'] or any(existing.payload.get(k) != command['payload'].get(k) for k in ('evidence_id', 'asset_id', 'freight_gross', 'carrier_retention', 'deductions', 'reported_payout')):
                    reasons.append('posted_source_difference')
        if matching:
            # Reversed events remain matches: a reviewed revision is needed, never a re-import.
            reasons.append('existing_posting_requires_review' if reasons else 'already_posted')
        reasons = sorted(set(reasons))
        status = ('posted_needs_review' if len(reasons) > 1 else 'already_posted') if matching else ('blocked' if reasons else 'candidate_for_review')
        if status == 'candidate_for_review':
            p = command['payload']
            lines = [f.line('receivable', p['reported_payout'], row['asset_id']),
                     f.line('freight', -f.D(p['freight_gross']), row['asset_id']),
                     f.line('carrier', p['carrier_retention'], row['asset_id'])]
            lines += [f.line(f.EXPENSE_MAP.get(k, k), v, row['asset_id']) for k, v in p['deductions'].items()]
            assert sum((l['debit'] - l['credit'] for l in lines), f.ZERO) == 0
            lines = [{**l, 'debit': f.money(l['debit']), 'credit': f.money(l['credit'])} for l in lines]
        result.append({**row, 'plan_status': status, 'blocking_reasons': reasons,
                       'existing_event_ids': [e.id for e in matching],
                       'proposed_command': command if status == 'candidate_for_review' else None,
                       'proposed_lines': lines, 'automatic_posting_allowed': False})
    candidates = [r for r in result if r['plan_status'] == 'candidate_for_review']
    return {'version': VERSION, 'tenant_id': tenant, 'scope': 'all_historical_source_settlements',
            'period': history['period'], 'basis': 'statement_date_draft_accrual',
            'evidence_status': 'review_required', 'posted': 0,
            'coverage': history['coverage'], 'counts': dict(Counter(r['plan_status'] for r in result)),
            'blocking_counts': dict(Counter(k for r in result for k in r['blocking_reasons'])),
            'candidate_totals': {k: f.money(sum((f.D(r[k]) for r in candidates), f.ZERO)) for k in ('freight', 'carrier', 'remainder')},
            'rows': result, 'limitations': history['limitations'] + [
                'Candidates require mapping and accounting-date approval; this endpoint writes nothing.',
                'Trailer assignments, reserves, financing and payments are not inferred from legacy allocations.',
                'Existing postings, including reversed or amended sources, require revision review.',
                'Readiness does not establish complete outside costs or available owner cash.']}
