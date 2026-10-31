"""Known historical cash payments never assert unknown cash funding or balances."""
from datetime import date
from decimal import Decimal
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.schemas.dieselbridge_financial import HistoricalBusinessCashPayment, RepairPaymentReversal, VerifiedRepairPayment
from app.models.dieselbridge import DieselBridgeRepairLink as Link, DieselBridgeRepairPayment as Payment
from app.models.finance import FinanceEvent, FinanceEvidence
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.services import dieselbridge_financial as f
from app.services import finance
from tests.test_dieselbridge_financial import setup, source, snapshot, sync
from tests.test_dieselbridge_settlement import settled, payment


def prepare(monkeypatch,db):
    monkeypatch.setenv('ELIS_DIESELBRIDGE_HISTORICAL_CASH_ENABLED','1')
    p=payment(amount='1000.00')
    source(monkeypatch,snapshot([settled(payments=[p])]))
    sync(db);db.commit()
    link=db.query(Link).one()
    body=HistoricalBusinessCashPayment(expected_revision=link.accepted_revision,amount='1000.00',paid_date='2026-10-20',
        source_attempt_id=p['attempt_id'],source_attempt_revision=p['revision'],
        business_cash_handover_confirmed=True,actual_handover_date_confirmed=True,
        unreconciled_cash_coverage_acknowledged=True,note='Owner confirms actual cash handed on this date; cashbook balances unavailable.')
    return link,body


def test_historical_receipt_clears_payable_and_reserve_once_without_invented_cashbook(monkeypatch,db):
    link,body=prepare(monkeypatch,db)
    result=f.record_historical_cash_payment(db,1,link.repair_id,body,'history','authenticated-owner');db.commit()
    assert result['recorded_paid_amount']=='1000.00' and result['recorded_balance_due']=='0.00'
    assert f.record_historical_cash_payment(db,1,link.repair_id,body,'history','authenticated-owner')==result
    assert db.query(Payment).count()==db.query(RepairReserveLedger).count()==1
    assert db.query(FinanceEvent).filter(FinanceEvent.kind.in_(['account','statement','journal'])).count()==0
    proof=db.query(FinanceEvidence).filter_by(extraction_version=f.HISTORICAL_CASH_VERSION).one()
    assert proof.extracted['historical_cash_review']['reviewer']=='authenticated-owner'
    assert proof.extracted['historical_cash_review']['funding_origin']=='not_established'
    ledger=finance.ledger_report(db,1,date.min,date(2026,10,31))
    assert ledger['ledger_payable']=='0.00' and ledger['ledger_owner_claims']=='0.00'
    assert ledger['income_statement']['net_income']=='-1000.00'  # no second expense
    assert ledger['balance_sheet']['difference']=='0.00'
    assert ledger['cash_flow']['operating']=='-1000.00'
    assert ledger['cash_flow']['balance_basis']=='unreconciled_ledger'
    assert ledger['cash_flow']['opening_balance'] is ledger['cash_flow']['closing_balance'] is None
    assert ledger['cash_flow']['ledger_closing_balance']=='-1000.00'
    cash=finance.cash_position(db,1,date(2026,10,31))
    assert cash['available'] is cash['business_cash'] is None
    assert cash['funding_ready'] is False
    assert cash['historical_cash_coverage']['amount']=='1000.00'
    with pytest.raises(HTTPException) as err:f.record_historical_cash_payment(db,1,link.repair_id,body,'duplicate','authenticated-owner')
    assert err.value.detail['code']=='DUPLICATE_SOURCE_PAYMENT'


@pytest.mark.parametrize('change',[{'transaction_id':'invented'},{'evidence_id':'invented'},{'owner_payment_confirmed':True}, {'source_attempt_id':None,'source_attempt_revision':None}])
def test_review_cannot_mix_cashbook_personal_or_unsourced_payment(monkeypatch,db,change):
    link,body=prepare(monkeypatch,db)
    with pytest.raises(HTTPException):f.record_historical_cash_payment(db,1,link.repair_id,body.model_copy(update=change),'bad','owner')
    assert db.query(Payment).count()==db.query(RepairReserveLedger).count()==0


def test_disabled_review_and_false_attestations_fail(monkeypatch,db):
    link,body=prepare(monkeypatch,db)
    monkeypatch.delenv('ELIS_DIESELBRIDGE_HISTORICAL_CASH_ENABLED')
    with pytest.raises(HTTPException) as err:f.record_historical_cash_payment(db,1,link.repair_id,body,'off','owner')
    assert err.value.status_code==503
    for key in ['business_cash_handover_confirmed','actual_handover_date_confirmed','unreconciled_cash_coverage_acknowledged']:
        with pytest.raises(ValidationError):HistoricalBusinessCashPayment(**{**body.model_dump(),key:False})
    assert db.query(Payment).count()==0


def test_source_changes_and_wrong_amount_cannot_use_exception(monkeypatch,db):
    link,body=prepare(monkeypatch,db)
    with pytest.raises(HTTPException) as err:f.record_historical_cash_payment(db,1,link.repair_id,body.model_copy(update={'amount':'999.00'}),'bad','owner')
    assert err.value.detail['code']=='SOURCE_PAYMENT_AMOUNT_MISMATCH'
    source(monkeypatch,snapshot([settled(payments=[payment(amount='1000.00',state='reversed')])]))
    with pytest.raises(HTTPException):f.record_historical_cash_payment(db,1,link.repair_id,body,'changed','owner')
    assert db.query(Payment).count()==0


def test_reverse_preserves_review_and_restores_payable_reserve(monkeypatch,db):
    link,body=prepare(monkeypatch,db)
    f.record_historical_cash_payment(db,1,link.repair_id,body,'history','owner');db.commit()
    paid=db.query(Payment).one()
    f.reverse_verified_payment(db,1,link.repair_id,paid.id,RepairPaymentReversal(expected_revision=link.accepted_revision,
        reversal_date='2026-10-22',reason='Correct historical payment attestation'),'reverse');db.commit()
    assert db.query(FinanceEvidence).filter_by(extraction_version=f.HISTORICAL_CASH_VERSION).count()==1
    assert finance.cash_position(db,1,date(2026,10,21))['historical_cash_coverage']['count']==1
    assert finance.cash_position(db,1,date(2026,10,22))['historical_cash_coverage']['count']==0
    assert f.public_state(db,1,link)['recorded_balance_due']=='1000.00'
    assert sum((r.amount if r.entry_type=='withdrawal' else -r.amount for r in db.query(RepairReserveLedger)),Decimal('0'))==0


def test_ordinary_cash_still_requires_reconciled_cashbook(monkeypatch,db):
    link,body=prepare(monkeypatch,db)
    normal=VerifiedRepairPayment(**{k:v for k,v in body.model_dump().items() if k not in
        ('business_cash_handover_confirmed','actual_handover_date_confirmed','unreconciled_cash_coverage_acknowledged')})
    with pytest.raises(HTTPException) as err:f.record_verified_payment(db,1,link.repair_id,normal,'ordinary')
    assert 'unmatched reconciled transaction' in err.value.detail['message']
    db.rollback()
    assert db.query(Payment).count()==0


def test_tenant_scope_and_closed_period_remain_enforced(monkeypatch,db):
    link,body=prepare(monkeypatch,db)
    from app.models.tenant import Tenant
    db.add(Tenant(id=2,name='Other business',business_type='logistics'));db.commit()
    with pytest.raises(HTTPException) as err:f.record_historical_cash_payment(db,2,link.repair_id,body,'wrong-tenant','owner')
    assert err.value.status_code==404
    from app.models.finance import FinanceEvent
    db.add(FinanceEvent(tenant_id=1,key='closed-fixture',digest='e'*64,kind='close_period',effective_date=date(2026,10,31),
        payload={'kind':'close_period','start':'2026-10-01','end':'2026-10-31'}));db.commit()
    with pytest.raises(HTTPException) as err:f.record_historical_cash_payment(db,1,link.repair_id,body,'closed','owner')
    assert err.value.detail['code']=='PERIOD_CLOSED'
    db.rollback()
    assert db.query(Payment).count()==0


def test_historical_evidence_cannot_settle_other_bill_or_different_date(monkeypatch,db):
    link,body=prepare(monkeypatch,db)
    f.record_historical_cash_payment(db,1,link.repair_id,body,'history','owner');db.commit()
    proof=db.query(FinanceEvidence).filter_by(extraction_version=f.HISTORICAL_CASH_VERSION).one()
    payload={'payer':'cash','claim_id':link.bill_event_id,'amount':'1000.00','evidence_id':proof.id,'transaction_id':None}
    with pytest.raises(HTTPException) as err:f.validate_historical_cash_evidence(db,1,payload,date(2026,10,21))
    assert err.value.detail['code']=='PAYMENT_EVIDENCE_REQUIRED'
    with pytest.raises(HTTPException):f.validate_historical_cash_evidence(db,1,{**payload,'claim_id':'another-bill'},body.paid_date)


def test_failed_projection_rolls_back_payment_proof_and_reserve(monkeypatch,db):
    link,body=prepare(monkeypatch,db)
    from app.services import accounting_service
    def broken(*args,**kwargs):raise RuntimeError('synthetic accounting failure')
    monkeypatch.setattr(accounting_service,'create_dieselbridge_payment_journal',broken)
    with pytest.raises(RuntimeError):f.record_historical_cash_payment(db,1,link.repair_id,body,'failure','owner')
    db.rollback()
    assert db.query(Payment).count()==db.query(RepairReserveLedger).count()==0
    assert db.query(FinanceEvent).filter_by(kind='payment').count()==0
    assert db.query(FinanceEvidence).filter_by(extraction_version=f.HISTORICAL_CASH_VERSION).count()==0


def test_fifteen_receipts_total_19262_85_and_all_known_handover_dates(monkeypatch,db):
    from tests.test_dieselbridge_financial import digest
    monkeypatch.setenv('ELIS_DIESELBRIDGE_HISTORICAL_CASH_ENABLED','1')
    # Production-approved amounts and date groups; fixture-only identities.
    groups=[('2026-09-12',['2480.61','605.55','226.28','1629.00','4886.38','358.72','1072.05','207.50']),
            ('2026-10-21',['252.70','2491.97']),
            ('2026-10-29',['3405.91','130.05','213.80','308.80','993.53'])]
    rows=[];dates={};attempts={}
    for day,amounts in groups:
        for amount in amounts:
            n=len(rows)+1;p=payment(n,amount=amount)
            row=settled(principal=amount,maxfee='0.00',payments=[p])
            row.update(repair_order_id=f'ro-{n}',order_number=f'RO{n}',work_completed_at='2026-04-20T12:00:00+00:00',service_date='2026-04-20')
            row['invoice'].update(invoice_id=f'invoice-{n}',invoice_number=f'INV{n}',invoice_date='2026-04-20')
            row['invoice']['revision']=digest({k:v for k,v in row['invoice'].items() if k!='revision'})
            row['revision']=digest({k:v for k,v in row.items() if k not in ('revision','settlement')})
            dates[row['repair_order_id']]=day;attempts[row['repair_order_id']]=p;rows.append(row)
    source(monkeypatch,snapshot(rows));sync(db);db.commit()
    for link in db.query(Link).order_by(Link.id).all():
        p=attempts[link.repair_order_id]
        body=HistoricalBusinessCashPayment(expected_revision=link.accepted_revision,amount=p['gross_received_amount'],
            paid_date=dates[link.repair_order_id],source_attempt_id=p['attempt_id'],source_attempt_revision=p['revision'],
            business_cash_handover_confirmed=True,actual_handover_date_confirmed=True,
            unreconciled_cash_coverage_acknowledged=True,note='Owner confirmed recorded date was actual business cash handover date.')
        f.record_historical_cash_payment(db,1,link.repair_id,body,'history-'+link.repair_order_id,'authenticated-owner')
    db.commit()
    assert db.query(Payment).count()==db.query(RepairReserveLedger).count()==15
    assert sum((p.amount for p in db.query(Payment)),Decimal('0'))==Decimal('19262.85')
    assert sum((p.amount for p in db.query(Payment).filter_by(paid_date=date(2026,9,12))),Decimal('0'))==Decimal('11466.09')
    assert {p.paid_date for p in db.query(Payment)}=={date(2026,9,12),date(2026,10,21),date(2026,10,29)}
    assert finance.ledger_report(db,1,date.min,date(2026,10,31))['ledger_payable']=='0.00'
    assert all(f.public_state(db,1,l)['historical_cash_coverage']['status']=='unreconciled' for l in db.query(Link))
