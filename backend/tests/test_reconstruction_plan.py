import base64
import hashlib
from copy import deepcopy
from datetime import date
from app.models.finance import FinanceEvidence, FinanceEvent
from app.services import reconstruction_plan as service
from tests.test_settlement_history import sample
from app.services.settlement_history import review_rows


def setup_source(db, monkeypatch):
    record, source = sample()
    proposal = source['proposal']
    proposal.update(kind='settlement', source_ref='77cargo:42', period_start='2026-09-14', period_end='2026-09-21')
    proposal['loads'][0]['source_row'] = 'original load row'
    proposal['fuel'][0]['source_row'] = 'original fuel row'
    raw = b'original source bytes'
    doc = FinanceEvidence(tenant_id=1, sha256=hashlib.sha256(raw).hexdigest(), filename='original.pdf', media_type='application/pdf', content_base64=base64.b64encode(raw).decode(), source_key='legacy-settlement:1', extraction_version='test', extracted={'proposal': proposal})
    db.add(doc); db.flush()
    source.update(id=doc.id, sha256=doc.sha256)
    rows = review_rows([record], {1: source})
    monkeypatch.setattr(service, 'settlement_history', lambda db, tenant: {'rows': rows, 'period': {'start': record['settlement_date'], 'end': record['settlement_date']}, 'coverage': {}, 'limitations': []})
    return doc, rows


def test_plan_is_read_only_balanced_and_retains_unknown_fuel(db, monkeypatch):
    doc, rows = setup_source(db, monkeypatch)
    before = db.query(FinanceEvent).count()
    plan = service.reconstruction_plan(db, 1)
    row = plan['rows'][0]
    assert plan['counts'] == {'candidate_for_review': 1}
    assert row['proposed_command']['payload']['fuel'][0]['product'] == 'unknown'
    assert row['measured_mpg'] is None and not row['automatic_posting_allowed']
    from decimal import Decimal
    assert sum(Decimal(l['debit']) - Decimal(l['credit']) for l in row['proposed_lines']) == 0
    assert plan['candidate_totals']['remainder'] == '500.00'
    assert db.query(FinanceEvent).count() == before
    assert service.reconstruction_plan(db, 1) == plan


def test_review_exceptions_and_closed_period_withhold_commands(db, monkeypatch):
    doc, rows = setup_source(db, monkeypatch)
    rows[0]['issues'].append({'code': 'service_date'})
    db.add(FinanceEvent(tenant_id=1, key='close-test', digest='test', kind='close_period', effective_date=date(2026, 9, 30), payload={'start':'2026-09-01', 'end':'2026-09-30'})); db.flush()
    result = service.reconstruction_plan(db, 1)['rows'][0]
    assert result['plan_status'] == 'blocked'
    assert {'service_date', 'closed_period'} <= set(result['blocking_reasons'])
    assert result['proposed_command'] is None and not result['proposed_lines']


def test_existing_posting_is_not_proposed_again(db, monkeypatch):
    doc, rows = setup_source(db, monkeypatch)
    db.add(FinanceEvent(tenant_id=1, key='posted-test', digest='test', kind='settlement', effective_date=date(2026, 9, 21), payload={**doc.extracted['proposal'], 'legacy_id':1, 'asset_id':1, 'evidence_id':doc.id})); db.flush()
    row = service.reconstruction_plan(db, 1)['rows'][0]
    assert row['plan_status'] == 'already_posted'
    assert row['proposed_command'] is None and len(row['existing_event_ids']) == 1


def test_duplicate_reference_cannot_be_candidate(db, monkeypatch):
    doc, rows = setup_source(db, monkeypatch)
    other = deepcopy(rows[0]); other['id'] = 2; rows.append(other)
    assert all('non_unique_source_reference' in r['blocking_reasons'] for r in service.reconstruction_plan(db, 1)['rows'])


def test_corrupted_original_is_blocked(db, monkeypatch):
    doc, rows = setup_source(db, monkeypatch)
    # In-memory corruption simulates invalid imported evidence without mutating stored history.
    from sqlalchemy.orm.attributes import set_committed_value
    set_committed_value(doc, 'content_base64', base64.b64encode(b'wrong bytes').decode())
    row = service.reconstruction_plan(db, 1)['rows'][0]
    assert 'source_hash_mismatch' in row['blocking_reasons']
    assert row['plan_status'] == 'blocked'


def test_plan_route_enforces_scope(client, monkeypatch):
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS','1')
    monkeypatch.setenv('APP_AUTH_TENANT_IDS','1')
    assert client.get('/api/v1/accounting/reconstruction-plan', headers={'X-Tenant-ID':'1'}).status_code == 200
    assert client.get('/api/v1/accounting/reconstruction-plan', headers={'X-Tenant-ID':'2'}).status_code == 404
    assert client.get('/api/v1/accounting/reconstruction-plan', headers={'X-Tenant-ID':'1'}, params={'tenant_id':2}).status_code == 400


def test_amended_posting_is_reviewed_not_reimported(db, monkeypatch):
    doc, rows = setup_source(db, monkeypatch)
    payload = {**doc.extracted['proposal'], 'legacy_id':1, 'asset_id':1, 'evidence_id':'prior-version'}
    db.add(FinanceEvent(tenant_id=1, key='amended-posting', digest='test', kind='settlement', effective_date=date(2026,9,21), payload=payload)); db.flush()
    row = service.reconstruction_plan(db, 1)['rows'][0]
    assert row['plan_status'] == 'posted_needs_review'
    assert 'posted_source_difference' in row['blocking_reasons']
    assert row['proposed_command'] is None


def test_unsupported_expense_mapping_is_withheld(db, monkeypatch):
    doc, rows = setup_source(db, monkeypatch)
    from sqlalchemy.orm.attributes import set_committed_value
    extracted = deepcopy(doc.extracted)
    extracted['proposal']['deductions']['unclassified_charge'] = '0.00'
    set_committed_value(doc, 'extracted', extracted)
    result = service.reconstruction_plan(db, 1)['rows'][0]
    assert 'expense_mapping_required' in result['blocking_reasons']
    assert result['proposed_command'] is None
