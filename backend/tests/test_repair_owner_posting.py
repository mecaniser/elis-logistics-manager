from datetime import date
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from app.models.finance import FinancePosting, FinanceEvent
from app.services import finance as f
from app.services.repair_confirmation import save_confirmation
from app.services.repair_owner_posting import process_confirmed, match_reimbursement, ReimbursementMatch
from app.services.repair_history import repair_history
from tests.test_repair_history import repair
from tests.test_repair_confirmation import payload
from tests.test_finance import truck, bank, cmd


def personal(db, **changes):
    return payload(db).model_copy(update={'source':'personal', 'reimbursement':'owed', 'paid_date':date(2026,9,21), **changes})


def test_personal_payment_and_reimbursement_once(db, truck):
    repair(db, truck)
    request = personal(db)
    first = save_confirmation(db, 1, request); db.commit()
    assert first['posted']
    assert db.query(FinancePosting).count() == 2
    assert save_confirmation(db, 1, request)['posted']
    assert db.query(FinancePosting).count() == 2
    claim_id = first['accounting'][0]['owner_claim_id']
    a, statement = bank(db, rows='2026-09-21,-200.00,Reimburse owner,r1\n', closing='9800.00')
    tx = statement.payload['_transactions'][0]['id']
    request_match = ReimbursementMatch(transaction_id=tx, amount='200.00')
    match_reimbursement(db, 1, claim_id, request_match, 'owner-match-once'); db.commit()
    match_reimbursement(db, 1, claim_id, request_match, 'owner-match-once'); db.commit()
    s = f.state(db, 1, date(2026,9,21))
    assert s['claims'][claim_id]['remaining'] == 300
    report = f.ledger_report(db,1,date(2026,1,1),date(2026,9,21))
    assert report['income_statement']['operating_earnings'] == '-500.00'
    assert db.query(FinancePosting).count() == 3
    with pytest.raises(HTTPException): match_reimbursement(db, 1, claim_id, request_match, 'duplicate-new-key')


def test_partial_keeps_vendor_and_owner_separate(db, truck):
    repair(db, truck)
    result = save_confirmation(db,1,personal(db,status='partial',paid_amount=f.D('200.00'))); db.commit()
    s = f.state(db,1,date(2026,9,21))
    assert sum(c['remaining'] for c in s['claims'].values() if c['creditor']=='vendor') == 300
    assert sum(c['remaining'] for c in s['claims'].values() if c['creditor']=='owner') == 200
    assert result['posted']


@pytest.mark.parametrize('changes', [{'paid_date':None}, {'reimbursement':'unknown'}, {'reimbursement':'reimbursed'}, {'source':'business','reimbursement':'unknown'}])
def test_incomplete_or_nonpersonal_does_not_post(db,truck,changes):
    repair(db,truck)
    result = save_confirmation(db,1,personal(db,**changes)); db.commit()
    assert not result['posted']
    assert db.query(FinancePosting).count() == 0


def test_notes_correction_retains_posting_but_money_change_requires_review(db,truck):
    repair(db,truck)
    save_confirmation(db,1,personal(db)); db.commit()
    result = save_confirmation(db,1,personal(db,note='Added card reference')); db.commit()
    assert result['posted']
    result = save_confirmation(db,1,personal(db,status='partial',paid_amount=f.D('100.00'))); db.commit()
    assert result['accounting'][0]['status'] == 'review_required'
    assert db.query(FinancePosting).count() == 2


def test_atomic_failure_retains_confirmation_without_half_posting(db,truck):
    repair(db,truck)
    original = f.append_command
    def fail_payment(db,tenant,command,key):
        if command.payload.kind == 'payment': f.fail('Synthetic payment failure')
        return original(db,tenant,command,key)
    with patch.object(f, 'append_command', side_effect=fail_payment):
        result = save_confirmation(db,1,personal(db)); db.commit()
    assert result['accounting'][0]['status'] == 'review_required'
    assert db.query(FinancePosting).count() == db.query(FinanceEvent).count() == 0
    assert repair_history(db,1,date.today())['rows'][0]['confirmation']
    assert process_confirmed(db,1)[0]['status'] == 'posted'


def test_closed_period_is_review_not_silent_backfill(db,truck):
    repair(db,truck)
    db.add(FinanceEvent(tenant_id=1,key='test-close',digest='x',kind='close_period',effective_date=date(2026,9,22),payload={'start':'2026-09-01','end':'2026-09-21'}));db.commit()
    result=save_confirmation(db,1,personal(db));db.commit()
    assert not result['posted']
    assert 'closed' in result['accounting'][0]['reason']
    assert db.query(FinancePosting).count()==0


def test_existing_repair_obligation_and_cross_business_fail_closed(db,truck):
    repair(db,truck)
    result=save_confirmation(db,1,personal(db));db.commit()
    from app.models.tenant import Tenant
    db.add(Tenant(id=2,name='Other',business_type='logistics'));db.commit()
    assert process_confirmed(db,2)==[]
    claim=result['accounting'][0]['owner_claim_id']
    with pytest.raises(HTTPException):match_reimbursement(db,2,claim,ReimbursementMatch(transaction_id='wrong',amount='1.00'),'wrong-tenant-key')


def test_bulk_historical_confirmation_posts_once_and_rejects_stale(db,truck,client,monkeypatch):
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS','1')
    monkeypatch.setenv('APP_AUTH_TENANT_IDS','1')
    repair(db,truck)
    save_confirmation(db,1,personal(db,reimbursement='unknown'));db.commit()
    row=repair_history(db,1,date.today())['rows'][0]
    body={'items':[{'repair_id':row['legacy_id'],'snapshot':row['review_snapshot'],'previous_id':row['confirmation']['id']}]}
    headers={'X-Tenant-ID':'1'}
    path='/api/v1/accounting/repair-owner-postings/confirm-unreimbursed'
    assert client.post(path,json=body,headers={'X-Tenant-ID':'2'}).status_code==404
    assert client.post(path,json=body,headers=headers).status_code==200
    assert client.post(path,json=body,headers=headers).status_code==200
    assert db.query(FinancePosting).count()==2
    assert client.get('/api/v1/accounting/owner-reimbursements',headers=headers).json()['total_owed']=='500.00'
    body['items'][0]['snapshot']='changed'
    assert client.post(path,json=body,headers=headers).status_code==409


def test_existing_manual_claim_is_not_duplicated(db,truck):
    from tests.test_finance import doc
    r=repair(db,truck)
    cmd(db,'bill',evidence_id=doc(db),source_ref='manual-repair',description='Repair',amount='500.00',category='repairs',asset_id=truck.id,legacy_repair_id=r.id)
    result=save_confirmation(db,1,personal(db));db.commit()
    assert result['accounting'][0]['status']=='review_required'
    assert db.query(FinancePosting).count()==1
