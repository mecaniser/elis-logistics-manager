"""Business cash is counted evidence; paying an incurred cost is not another expense."""
from datetime import date
import pytest
from fastapi import HTTPException
from app.schemas.finance import Command
from app.services import finance as f
from app.models.finance import FinanceEvent
from tests.test_finance import truck, cmd, doc, bank, bill, policy_setup, ASOF


def cashbook(db, rows='', opening='1000.00', closing='1000.00', count=True):
    account = cmd(db, 'account', when='2026-01-01', name='Business cash box', account_type='cash')
    mapping = cmd(db, 'csv_mapping', when='2026-01-01', name='Cash log', date_column='Date', amount_column='Amount', description_column='Description', id_column='ID')
    source = doc(db, ('Date,Amount,Description,ID\n' + rows).encode())
    args = dict(account_id=account.id, mapping_id=mapping.id, evidence_id=source, start=str(ASOF), end=str(ASOF), opening=opening, closing=closing)
    if count: args['cash_count_evidence_id'] = doc(db, b'Signed closing cash count')
    statement = cmd(db, 'statement', **args)
    return account, statement


def test_cash_count_required_without_inventing_balance(db, truck):
    with pytest.raises(HTTPException) as exc:
        cashbook(db, count=False)
    assert exc.value.detail['code'] == 'CASH_COUNT_REQUIRED'
    assert f.cash_position(db, 1, ASOF)['business_cash'] is None


def test_cash_repair_partial_payment_and_idempotency(db, truck):
    d = policy_setup(db)
    _, st = cashbook(db, rows=f'{ASOF},-200.00,Repair cash receipt,r1\n', closing='800.00')
    b = bill(db, d, truck)
    payment = dict(kind='payment', claim_id=b.id, amount='200.00', payer='cash', transaction_id=st.payload['_transactions'][0]['id'])
    first = cmd(db, key='cash-repair', **payment)
    assert cmd(db, key='cash-repair', **payment).id == first.id
    c = f.cash_position(db, 1, ASOF)
    assert c['business_cash'] == '800.00'
    assert c['uncovered_bills'] == '300.00'
    assert c['available'] == '500.00'
    assert f.ledger_report(db, 1, date.min, ASOF)['income_statement']['net_income'] == '-500.00'
    with pytest.raises(HTTPException): cmd(db, **payment)


def test_cash_payer_must_match_account_type(db, truck):
    d = policy_setup(db)
    _, st = bank(db, rows=f'{ASOF},-200.00,Zelle,r1\n', closing='9800.00')
    b = bill(db, d, truck)
    with pytest.raises(HTTPException):
        cmd(db, 'payment', claim_id=b.id, amount='200.00', payer='cash', transaction_id=st.payload['_transactions'][0]['id'])
    cmd(db, 'payment', claim_id=b.id, amount='200.00', payer='business', transaction_id=st.payload['_transactions'][0]['id'])
    assert f.cash_position(db, 1, ASOF)['uncovered_bills'] == '300.00'


def test_bank_to_cash_transfer_preserves_total_and_creates_no_income(db, truck):
    policy_setup(db)
    _, bs = bank(db, rows=f'{ASOF},-500.00,ATM withdrawal,b1\n', closing='9500.00')
    _, cs = cashbook(db, rows=f'{ASOF},500.00,ATM cash received,c1\n', opening='0.00', closing='500.00')
    cmd(db, 'bank_match', transaction_id=bs.payload['_transactions'][0]['id'], counterpart_transaction_id=cs.payload['_transactions'][0]['id'], match_type='transfer')
    assert f.cash_position(db, 1, ASOF)['business_cash'] == '10000.00'
    assert len(f.state(db, 1, ASOF)['matches']) == 2
    assert f.ledger_report(db, 1, date.min, ASOF)['income_statement']['net_income'] == '0.00'


def test_personal_cash_then_cash_reimbursement_one_expense(db, truck):
    d = policy_setup(db)
    _, cs = cashbook(db, rows=f'{ASOF},-500.00,Owner reimbursement,c1\n', closing='500.00')
    b = bill(db, d, truck)
    p = cmd(db, 'payment', claim_id=b.id, amount='500.00', payer='owner', evidence_id=d)
    cmd(db, 'payment', claim_id=p.id, amount='500.00', payer='cash', transaction_id=cs.payload['_transactions'][0]['id'])
    cash = f.cash_position(db, 1, ASOF)
    assert cash['owner_reimbursement'] == '0.00'
    assert cash['available'] == '500.00'
    assert f.ledger_report(db, 1, date.min, ASOF)['income_statement']['net_income'] == '-500.00'


def test_cashbook_cannot_spend_missing_funding(db, truck):
    with pytest.raises(HTTPException) as exc:
        cashbook(db, rows=f'{ASOF},-500.00,Repair,c1\n{ASOF},500.00,Later funding,c2\n', opening='0.00', closing='0.00')
    assert exc.value.detail['code'] == 'CASH_SHORTFALL'


def test_pre_cashbook_statement_digest_still_replays(db, truck):
    _, st = bank(db)
    payload = {k:v for k,v in st.payload.items() if not k.startswith('_')}
    assert 'cash_count_evidence_id' not in payload
    command = Command(effective_date=ASOF, payload=payload)
    assert f.append_command(db, 1, command, st.key).id == st.id


def test_reserve_funded_cash_payment_does_not_reduce_available_twice(db, truck):
    d = policy_setup(db)
    a, first = cashbook(db)
    r = cmd(db, 'reserve', pair_id=truck.id, purpose='repair', amount='500.00', opening=True, note='Confirmed earmark', evidence_id=d)
    b = bill(db, d, truck, reserve_id=r.id)
    assert f.cash_position(db, 1, ASOF)['available'] == '500.00'
    later = '2026-09-22'
    source = doc(db, f'Date,Amount,Description,ID\n{later},-500.00,Repair,c2\n'.encode())
    st = cmd(db, 'statement', when=later, account_id=a.id, mapping_id=first.payload['mapping_id'], evidence_id=source, cash_count_evidence_id=first.payload['cash_count_evidence_id'], start=later, end=later, opening='1000.00', closing='500.00')
    cmd(db, 'payment', when=later, claim_id=b.id, amount='500.00', payer='cash', transaction_id=st.payload['_transactions'][0]['id'])
    cash = f.cash_position(db, 1, date.fromisoformat(later))
    assert cash['protected_reserves'] == '0.00'
    assert cash['available'] == '500.00'


def test_repeated_cashbook_import_does_not_duplicate_transactions(db, truck):
    _, st = cashbook(db, rows=f'{ASOF},-200.00,Repair,c1\n', closing='800.00')
    payload = {k:v for k,v in st.payload.items() if not k.startswith('_')}
    before = db.query(FinanceEvent).count()
    with pytest.raises(HTTPException) as exc: cmd(db, **payload)
    assert exc.value.detail['code'] == 'DUPLICATE_TRANSACTION'
    assert db.query(FinanceEvent).count() == before


def test_cash_count_must_be_tenant_owned(db, truck):
    from app.models.tenant import Tenant
    from app.models.finance import FinanceEvidence
    db.add(Tenant(id=2, name='Other', business_type='logistics')); db.commit()
    other = FinanceEvidence(tenant_id=2, sha256='a'*64, filename='count.txt', media_type='text/plain', content_base64='eA==', source_key='other-count', extraction_version='test', extracted={})
    db.add(other); db.commit()
    _, st = cashbook(db)
    payload = {k:v for k,v in st.payload.items() if not k.startswith('_')}
    payload['cash_count_evidence_id'] = other.id
    with pytest.raises(HTTPException) as exc: cmd(db, **payload)
    assert exc.value.status_code == 404


def test_workspace_repair_choices_stay_tenant_scoped(db, truck, client, monkeypatch):
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS', '1')
    monkeypatch.setenv('APP_AUTH_TENANT_IDS', '1')
    from app.models.repair import Repair
    from app.models.tenant import Tenant
    from app.models.truck import Truck
    db.add(Tenant(id=2, name='Other', business_type='logistics')); db.commit()
    other = Truck(name='Other truck', tenant_id=2, vehicle_type='truck'); db.add(other); db.flush()
    own = Repair(truck_id=truck.id, title='Own repair', repair_date=ASOF, cost='500.00')
    db.add_all([own, Repair(truck_id=other.id, title='Private other repair', repair_date=ASOF, cost='999.00')]); db.commit()
    response = client.get('/api/v1/accounting/workspace', params={'as_of':str(ASOF)}, headers={'X-Tenant-ID':'1'})
    assert response.status_code == 200
    assert [r['id'] for r in response.json()['legacy_repairs']] == [own.id]


def test_cash_count_is_preserved_in_report_evidence_manifest(db, truck):
    _, st = cashbook(db)
    result = f.report(db, 1, ASOF, ASOF, ASOF)
    ids = {item['id'] for item in result['evidence_manifest']}
    assert {st.payload['cash_count_evidence_id'], st.payload['evidence_id']} <= ids
