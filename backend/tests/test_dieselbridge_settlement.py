"""Quoted maximum card surcharge must never become an uncharged cash expense."""
import asyncio
from copy import deepcopy
from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.exc import IntegrityError
from app.models.dieselbridge import DieselBridgeRepairLink as Link,DieselBridgeRepairPayment as Payment
from app.models.finance import FinanceEvent,FinancePosting,FinanceEvidence
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.services import dieselbridge_financial as financial
from app.schemas.dieselbridge_financial import VerifiedRepairPayment,RepairPaymentReversal
from app.schemas.finance import Command
from app.services import finance as f
from tests.test_dieselbridge_financial import setup,source,snapshot,item,sync,digest,receipt


def payment(n=1,amount='200.00',rail='cash',fee='0.00',state='confirmed',**changes):
    p={'attempt_id':f'attempt-{n}','rail':rail,'state':state,'principal_amount':amount,'received_amount':amount,
       'gross_received_amount':f.money(Decimal(amount)+Decimal(fee)),'applied_principal_amount':amount,
       'applied_card_fee_amount':fee,'applied_card_fee_tax_amount':'0.00','unapplied_amount':'0.00',
       'confirmed_at':'2026-10-21T03:00:00+00:00','actual_paid_date':None,'paid_date_basis':'unknown',**changes}
    p['revision']=digest(p);return p


def settled(principal='1000.00',maxfee='35.00',payments=None,tax='0.00',**changes):
    payments=payments or []
    total=f.money(Decimal(principal)+Decimal(maxfee))
    row=item(total=total)
    row['invoice']['breakdown']={'subtotal':f.money(Decimal(principal)-Decimal(tax)),'shop_supplies_amount':'0.00','service_fee_amount':maxfee,'tax_amount':tax,'discount_amount':'0.00'}
    row['invoice']['revision']=digest({k:v for k,v in row['invoice'].items() if k!='revision'})
    confirmed=sum((Decimal(p['applied_principal_amount']) for p in payments if p['state']=='confirmed'),Decimal('0'))
    s={'settlement_id':'settlement-1','status':'available','review_reasons':[],
       'source_state':'paid' if confirmed==Decimal(principal) else 'partially_paid' if confirmed else 'unpaid',
       'principal_total':principal,'max_card_fee':maxfee,'max_card_fee_tax':'0.00','confirmed_principal':f.money(confirmed),
       'pending_principal':'0.00','unapplied_credit':'0.00','refund_pending':'0.00','payments':payments,**changes}
    s['revision']=digest(s);row['settlement']=s
    row['revision']=digest({k:v for k,v in row.items() if k not in ('revision','settlement')});return row


def verified(db,link,p,proof=None,key='verified-source',amount=None):
    proof=proof or receipt(db,key)
    body=VerifiedRepairPayment(expected_revision=link.accepted_revision,amount=amount or p['gross_received_amount'],paid_date='2026-10-20',payer='owner',evidence_id=proof.id,owner_payment_confirmed=True,note='Actual personal payment verified against independent receipt',source_attempt_id=p['attempt_id'],source_attempt_revision=p['revision'])
    return financial.record_verified_payment(db,1,link.repair_id,body,key)


def test_cash_000017_quotes5057_but_books4886_and_zero_reserve(monkeypatch,db):
    row=settled('4886.38','171.02',[payment(amount='4886.38')])
    row['invoice']['breakdown'].update(subtotal='4844.38',shop_supplies_amount='42.00')
    row['invoice']['revision']=digest({k:v for k,v in row['invoice'].items() if k!='revision'});row['revision']=digest({k:v for k,v in row.items() if k not in ('revision','settlement')})
    source(monkeypatch,snapshot([row]));result=sync(db);db.commit()
    link=db.query(Link).one();state=financial.public_state(db,1,link)
    assert result['created']==1 and db.query(Repair).one().cost==Decimal('4886.38')
    assert state['source_invoice_total']=='5057.40' and state['booked_cost']=='4886.38'
    assert state['source_confirmed_amount']=='4886.38' and state['recorded_paid_amount']=='0.00'
    assert state['source_settlement']['payments'][0]['actual_paid_date'] is None
    assert db.query(FinanceEvent).filter_by(kind='payment').count()==db.query(RepairReserveLedger).count()==0


def test_partial_source_receipt_does_not_reduce_full_cost_and_refreshes_without_review(monkeypatch,db):
    row=settled(payments=[payment()]);source(monkeypatch,snapshot([row]));sync(db);db.commit()
    link=db.query(Link).one();revision=link.accepted_revision
    row2=settled(payments=[payment(),payment(2,'100.00')]);source(monkeypatch,snapshot([row2]));result=sync(db,'second');db.commit()
    assert result['unchanged']==1 and result['review_required']==0
    assert link.accepted_revision==revision and link.state=='active'
    state=financial.public_state(db,1,link)
    assert state['booked_cost']=='1000.00' and state['source_confirmed_amount']=='300.00' and state['source_recorded_balance']=='700.00'
    assert state['recorded_paid_amount']=='0.00' and state['recorded_balance_due']=='1000.00'
    assert db.query(FinanceEvidence).filter_by(extraction_version='db094-settlement-observation-v2').count()==1


def test_card_gross_receipt_contains_applied_fee_not_just_principal(monkeypatch,db):
    p=payment(amount='500.00',rail='card',fee='17.50');source(monkeypatch,snapshot([settled(payments=[p])]))
    sync(db);db.commit();link=db.query(Link).one()
    assert db.query(Repair).one().cost==Decimal('1017.50')
    with pytest.raises(HTTPException):verified(db,link,p,key='wrong-principal',amount='500.00')
    result=verified(db,link,p);db.commit()
    assert result['recorded_paid_amount']=='517.50' and result['recorded_balance_due']=='500.00'
    assert db.query(RepairReserveLedger).one().amount==Decimal('517.50')


def test_source_binding_retry_duplicate_and_reversal_release_claim(monkeypatch,db):
    p=payment();source(monkeypatch,snapshot([settled(payments=[p])]))
    sync(db);db.commit();link=db.query(Link).one();proof=receipt(db)
    result=verified(db,link,p,proof=proof);db.commit()
    assert verified(db,link,p,proof=proof)==result
    with pytest.raises(HTTPException) as exc:verified(db,link,p,key='duplicate-different-proof')
    assert exc.value.detail['code']=='DUPLICATE_SOURCE_PAYMENT';db.rollback()
    row=db.query(Payment).one()
    financial.reverse_verified_payment(db,1,link.repair_id,row.id,RepairPaymentReversal(expected_revision=link.accepted_revision,reversal_date='2026-10-22',reason='Correct mistaken funding'),'reverse');db.commit()
    verified(db,link,p,key='corrected-funding');db.commit()
    assert db.query(Payment).filter_by(reversal_event_id=None).count()==1
    assert sum(x.amount if x.entry_type=='withdrawal' else -x.amount for x in db.query(RepairReserveLedger))==Decimal('200.00')


def test_source_reversed_claim_preserves_booked_finance_and_requires_review(monkeypatch,db):
    p=payment();source(monkeypatch,snapshot([settled(payments=[p])]))
    sync(db);db.commit();link=db.query(Link).one();verified(db,link,p);db.commit()
    source(monkeypatch,snapshot([settled(payments=[payment(state='reversed')])]))
    assert sync(db,'reversed')['review_required']==1;db.commit()
    assert db.query(Repair).one().cost==Decimal('1000.00')
    assert db.query(Payment).one().reversal_event_id is None and db.query(RepairReserveLedger).one().amount==Decimal('200.00')
    assert financial.public_state(db,1,link)['source_payment_review_required']


@pytest.mark.parametrize('row,reason',[
    (settled(payments=[payment()],tax='10.00'),'cash_tax_policy_conflict'),
    (settled(refund_pending='1.00'),'source_payment_allocation_review_required'),
    (settled(payments=[payment(state='refunded')]),'source_payment_reversal_review_required'),
    (settled(confirmed_principal='50.00'),'source_payment_totals_inconsistent'),
])
def test_unsafe_source_financial_states_block_without_writes(monkeypatch,db,row,reason):
    source(monkeypatch,snapshot([row]));result=sync(db)
    assert result['blocked']==1
    assert db.query(Repair).count()==db.query(RepairReserveLedger).count()==0
    assert reason in financial.build_preview(db,1,__import__('tests.test_dieselbridge_financial',fromlist=['C']).C,snapshot([row]))['rows'][0]['blockers']


def test_v1_rejected_and_missing_settlement_fee_never_assumed_payable(monkeypatch,db):
    value=snapshot([item()]);value['version']='db094-repair-financial-v1';source(monkeypatch,value)
    with pytest.raises(HTTPException):sync(db)
    row=settled();row['settlement']=None;source(monkeypatch,snapshot([row]));assert sync(db,'missing')['blocked']==1
    assert db.query(Repair).count()==0


def test_claim_rechecks_fresh_source_before_posting_and_generic_evidence_reuse_cannot_bypass(monkeypatch,db):
    p=payment();source(monkeypatch,snapshot([settled(payments=[p])]))
    sync(db);db.commit();link=db.query(Link).one();verified(db,link,p);db.commit()
    evidence=db.query(Payment).one().evidence_id
    proof=receipt(db,'another')
    source(monkeypatch,snapshot([settled(payments=[payment(state='reversed')])]))
    before=db.query(FinanceEvent).count()
    with pytest.raises(HTTPException):verified(db,link,p,proof=proof,key='stale');db.rollback()
    assert db.query(FinanceEvent).count()==before
    with pytest.raises(HTTPException):
        f.append_command(db,1,Command(effective_date=date(2026,10,20),payload={'kind':'payment','claim_id':link.bill_event_id,'amount':'200.00','payer':'owner','evidence_id':evidence}),'generic-reuse')
    db.rollback();assert db.query(Payment).count()==1


def test_earned_card_fee_cost_change_requires_real_reviewed_replacement(monkeypatch,db):
    from app.schemas.dieselbridge_financial import SourceReviewApply
    source(monkeypatch,snapshot([settled()]));sync(db);db.commit()
    link=db.query(Link).one();source(monkeypatch,snapshot([settled(payments=[payment(rail='card',amount='500.00',fee='17.50')])]))
    assert sync(db,'earned-fee')['review_required']==1;db.commit()
    review,*_=asyncio.run(financial.review_preview(db,1,link.repair_id,link.accepted_revision))
    assert review['action']=='replace_unpaid_invoice' and review['after']['cost']=='1017.50'
    asyncio.run(financial.apply_source_review(db,1,link.repair_id,SourceReviewApply(expected_revision=link.accepted_revision,expected_review_digest=review['review_digest'],note='Reviewed newly incurred card surcharge'),'accept-earned-fee'));db.commit()
    assert db.query(Repair).one().cost==Decimal('1017.50') and link.state=='active'
    assert db.query(Payment).count()==db.query(RepairReserveLedger).count()==0


def test_revoked_scope_withholds_current_source_observations(monkeypatch,db):
    source(monkeypatch,snapshot([settled(payments=[payment()])]))
    sync(db);db.commit();link=db.query(Link).one()
    source(monkeypatch,snapshot([]));sync(db,'revoked');db.commit()
    state=financial.public_state(db,1,link)
    assert state['source_settlement'] is None and state['source_confirmed_amount'] is None and state['source_obligation_amount'] is None
    assert link.source_settlement_payload is not None and state['booked_cost']=='1000.00'


def test_resolved_cash_evidence_coverage_preserves_quote_without_false_difference(monkeypatch,db):
    from app.services.repair_history import repair_history
    source(monkeypatch,snapshot([settled('4886.38','171.02',[payment(amount='4886.38')])]))
    sync(db);db.commit()
    evidence=db.query(FinanceEvidence).filter_by(extraction_version='dieselbridge-financial-v1').one()
    assert evidence.extracted['invoice_review']['source_total']=='4886.38'
    assert evidence.extracted['invoice_review']['quoted_total']=='5057.40'
    report=repair_history(db,1,date(2026,10,30))
    row=next(r for r in report['rows'] if r['legacy_id']==db.query(Repair).one().id)
    assert 'invoice_amount_difference' not in row['issues'] and row['source_totals']==['4886.38']
    assert '"total_amount": "5057.40"' in __import__('base64').b64decode(evidence.content_base64).decode()
