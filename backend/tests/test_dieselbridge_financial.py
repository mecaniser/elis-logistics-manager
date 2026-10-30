import asyncio
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal
import httpx
import pytest
from fastapi import HTTPException
from app.models.dieselbridge import DieselBridgeRepairLink, DieselBridgeRepairPayment
from app.models.finance import FinanceEvent, FinanceLine, FinancePosting, FinanceEvidence
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.models.truck import Truck
from app.schemas.dieselbridge_financial import VerifiedRepairPayment, RepairPaymentReversal, SourceReviewApply
from app.services import dieselbridge as d
from app.services import dieselbridge_financial as financial
from app.services import finance as f

C={'tenant_id':1,'slug':'shop','shop_id':'shop-1','bill_to_id':'customer-1','base_url':'https://source.example','api_key_env':'TEST_DB094_FINANCIAL_KEY'}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()

def item(n=1,authorization='authorized',total='1000.00',**changes):
    inv={'invoice_id':f'invoice-{n}','invoice_number':f'INV-{n}','status':'current_finalized','invoice_date':'2026-10-19','invoice_date_basis':'native_issue_timestamp','currency':'USD','total_amount':total,'breakdown':{'subtotal':total,'shop_supplies_amount':'0.00','service_fee_amount':'0.00','tax_amount':'0.00','discount_amount':'0.00'},'line_items':{'labor':[{'description':'Transmission clutch replacement'}],'parts':[]},'pdf_sha256':None}
    inv['revision']=digest(inv)
    row={'repair_order_id':f'ro-{n}','order_number':f'RO-{n}','vehicle_id':'vehicle','vin':'VIN609','unit_number':'609','description':'Transmission clutch replacement','work_completed_at':'2026-10-01T12:00:00+00:00','service_date':'2026-10-01','authorization':authorization,'invoice':inv if authorization=='authorized' else None,'settlement':None,**changes}
    row['revision']=digest({k:v for k,v in row.items() if k!='settlement'})
    return row

def snapshot(items):
    body={'version':'db094-repair-financial-v2','shop_id':'shop-1','customer_id':'customer-1','items':items}
    return {**body,'complete':True,'count':len(items),'snapshot_id':digest(body)}

@pytest.fixture(autouse=True)
def setup(monkeypatch,db):
    monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','1')
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS',json.dumps([C]))
    monkeypatch.setenv('TEST_DB094_FINANCIAL_KEY','fixture-only')
    monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS','1')
    db.add(Truck(id=1,tenant_id=1,name='Volvo609',vehicle_type='truck',vin='VIN609'));db.commit()

def source(monkeypatch,value):
    async def request(self,path,params=None):
        assert path=='repair-orders/financial'
        return httpx.Response(200,json=value)
    monkeypatch.setattr(d.SourceClient,'request',request)

def sync(db,key='sync-1',**kwargs):
    return asyncio.run(financial.sync_financial(db,1,'shop',idempotency_key=key,automatic=True,**kwargs))

def test_new_finalized_cost_is_normal_repair_and_payable_not_payment(monkeypatch,db):
    source(monkeypatch,snapshot([item()]))
    result=sync(db)
    repair=db.query(Repair).one();link=db.query(DieselBridgeRepairLink).one()
    assert result['created']==1 and repair.repair_date==date(2026,10,1)
    assert repair.cost==Decimal('1000.00') and repair.category!='maintenance'
    assert repair.paid_from_reserve is False
    assert db.query(FinanceEvent).filter_by(kind='bill').count()==1
    assert db.query(FinanceEvent).filter_by(kind='payment').count()==0
    assert db.query(RepairReserveLedger).count()==0
    assert {x.account for x in db.query(FinanceLine).all()}=={'repairs','payable'}
    state=financial.public_state(db,1,link)
    assert state['payment_status']=='unconfirmed' and state['recorded_paid_amount']=='0.00'
    assert state['recorded_balance_due']=='1000.00'

def test_replay_and_new_request_create_no_duplicate_expense(monkeypatch,db):
    source(monkeypatch,snapshot([item()]))
    first=sync(db);second=sync(db);third=sync(db,'another-key')
    assert first==second and third['unchanged']==1
    assert db.query(Repair).count()==db.query(FinanceEvent).filter_by(kind='bill').count()==1

def test_history_metadata_or_owner_only_invoice_cannot_create_cost(monkeypatch,db):
    source(monkeypatch,snapshot([item(authorization='attribution_required')]))
    result=sync(db)
    assert result['blocked']==1
    assert db.query(Repair).count()==db.query(FinanceEvent).count()==0

def test_changed_or_removed_current_invoice_preserves_accepted_expense(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db)
    source(monkeypatch,snapshot([item(total='1200.00')]))
    assert sync(db,'change')['review_required']==1
    assert db.query(Repair).one().cost==Decimal('1000.00')
    assert db.query(DieselBridgeRepairLink).one().state=='review_required'
    source(monkeypatch,snapshot([]));assert sync(db,'absent')['review_required']==1
    assert db.query(Repair).one().cost==Decimal('1000.00')

def test_missing_source_scope_or_hash_rejected_without_writes(monkeypatch,db):
    value=snapshot([item()]);value['customer_id']='other';source(monkeypatch,value)
    with pytest.raises(HTTPException):sync(db)
    assert db.query(Repair).count()==0

def test_disabled_financial_feature_cannot_write(monkeypatch,db):
    monkeypatch.delenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED')
    source(monkeypatch,snapshot([item()]))
    with pytest.raises(HTTPException) as error:sync(db)
    assert error.value.status_code==503 and db.query(Repair).count()==0

def test_invoice_evidence_alone_cannot_establish_owner_payment(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db)
    link=db.query(DieselBridgeRepairLink).one()
    body=VerifiedRepairPayment(expected_revision=link.accepted_revision,amount='200.00',paid_date='2026-10-20',payer='owner',evidence_id=link.evidence_id,owner_payment_confirmed=True,note='Actual personal payment')
    with pytest.raises(HTTPException):financial.record_verified_payment(db,1,link.repair_id,body,'payment-1')
    assert db.query(DieselBridgeRepairPayment).count()==db.query(RepairReserveLedger).count()==0


def receipt(db,label='receipt'):
    import base64
    raw=('Actual payment receipt '+label).encode()
    value=FinanceEvidence(tenant_id=1,sha256=hashlib.sha256(raw).hexdigest(),filename=label+'.pdf',
        media_type='application/pdf',content_base64=base64.b64encode(raw).decode(),source_key=label,
        extraction_version='elis-evidence-v1',extracted={'status':'needs_review'})
    db.add(value);db.flush();return value


def owner_payment(db,link,amount='200.00',key='payment-1',proof=None,**changes):
    proof=proof or receipt(db,key)
    body=VerifiedRepairPayment(expected_revision=link.accepted_revision,amount=amount,paid_date='2026-10-20',
        payer='owner',evidence_id=proof.id,owner_payment_confirmed=True,note='Personally paid against this receipt',**changes)
    return financial.record_verified_payment(db,1,link.repair_id,body,key)


def test_partial_verified_owner_payment_and_reversal_are_exact_and_idempotent(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one()
    proof=receipt(db)
    first=owner_payment(db,link,proof=proof)
    assert first['recorded_paid_amount']=='200.00' and first['recorded_balance_due']=='800.00'
    assert first['payment_status']=='partial'
    assert owner_payment(db,link,proof=proof)==first
    assert db.query(RepairReserveLedger).one().amount==Decimal('200.00')
    assert db.query(RepairReserveLedger).one().entry_date==date(2026,10,20)
    assert db.query(Repair).one().paid_from_reserve is False
    payment=db.query(DieselBridgeRepairPayment).one()
    reversal=RepairPaymentReversal(expected_revision=link.accepted_revision,reversal_date='2026-10-21',reason='Incorrect receipt allocation corrected')
    result=financial.reverse_verified_payment(db,1,link.repair_id,payment.id,reversal,'reverse-1')
    assert result['recorded_paid_amount']=='0.00' and result['recorded_balance_due']=='1000.00'
    assert financial.reverse_verified_payment(db,1,link.repair_id,payment.id,reversal,'reverse-1')==result
    assert db.query(RepairReserveLedger).filter_by(entry_type='withdrawal').count()==1
    assert db.query(RepairReserveLedger).filter_by(entry_type='withdrawal_reversal').one().amount==Decimal('200.00')
    assert db.query(Repair).one().cost==Decimal('1000.00')


def test_repeated_owner_receipt_with_new_key_or_note_is_not_another_payment(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one();proof=receipt(db)
    owner_payment(db,link,proof=proof)
    body=VerifiedRepairPayment(expected_revision=link.accepted_revision,amount='200.00',paid_date='2026-10-20',
        payer='owner',evidence_id=proof.id,owner_payment_confirmed=True,note='Different note same payment')
    with pytest.raises(HTTPException) as error:financial.record_verified_payment(db,1,link.repair_id,body,'fresh-key')
    assert error.value.detail['code']=='DUPLICATE_PAYMENT'
    assert db.query(DieselBridgeRepairPayment).count()==1


@pytest.mark.parametrize('changes',[{'amount':'300.00'},{'paid_date':'2026-10-21'}])
def test_owner_receipt_cannot_be_reused_with_altered_amount_or_date(monkeypatch,db,changes):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one();proof=receipt(db)
    owner_payment(db,link,proof=proof)
    fields={'expected_revision':link.accepted_revision,'amount':'200.00','paid_date':'2026-10-20','payer':'owner','evidence_id':proof.id,
        'owner_payment_confirmed':True,'note':'Reusing the same receipt for another allocation',**changes}
    with pytest.raises(HTTPException) as error:financial.record_verified_payment(db,1,link.repair_id,VerifiedRepairPayment(**fields),'altered-receipt')
    assert error.value.detail['code']=='DUPLICATE_PAYMENT' and db.query(DieselBridgeRepairPayment).count()==1


def test_one_owner_receipt_cannot_fund_multiple_source_repairs(monkeypatch,db):
    source(monkeypatch,snapshot([item(),item(2)]));sync(db);links=db.query(DieselBridgeRepairLink).order_by(DieselBridgeRepairLink.id).all();proof=receipt(db)
    owner_payment(db,links[0],proof=proof)
    with pytest.raises(HTTPException) as error:owner_payment(db,links[1],proof=proof,key='other-repair')
    assert error.value.detail['code']=='DUPLICATE_PAYMENT'
    assert sum(p.amount for p in db.query(RepairReserveLedger))==Decimal('200.00')


def test_owner_receipt_reuse_is_allowed_only_after_explicit_reversal(monkeypatch,db):
    source(monkeypatch,snapshot([item(),item(2)]));sync(db);links=db.query(DieselBridgeRepairLink).order_by(DieselBridgeRepairLink.id).all();proof=receipt(db)
    owner_payment(db,links[0],proof=proof)
    payment=db.query(DieselBridgeRepairPayment).one()
    reverse=RepairPaymentReversal(expected_revision=links[0].accepted_revision,reversal_date='2026-10-21',reason='Correct receipt allocated to wrong repair')
    financial.reverse_verified_payment(db,1,links[0].repair_id,payment.id,reverse,'receipt-reallocation-reversal')
    result=owner_payment(db,links[1],proof=proof,key='corrected-repair')
    assert result['recorded_paid_amount']=='200.00'
    net=sum(x.amount if x.entry_type=='withdrawal' else -x.amount for x in db.query(RepairReserveLedger))
    assert net==Decimal('200.00')


def test_cloned_receipt_with_false_hash_or_generated_attestation_is_not_proof(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one();proof=receipt(db)
    clone=FinanceEvidence(tenant_id=1,sha256='f'*64,filename='clone.pdf',media_type='application/pdf',content_base64=proof.content_base64,
        source_key='cloned-receipt',extraction_version='elis-evidence-v1',extracted={})
    db.add(clone);db.flush()
    with pytest.raises(HTTPException) as error:owner_payment(db,link,proof=clone)
    assert error.value.detail['code']=='PAYMENT_EVIDENCE_INTEGRITY'
    owner_payment(db,link,proof=proof)
    generated=f.evidence(db,1,db.query(DieselBridgeRepairPayment).one().evidence_id)
    with pytest.raises(HTTPException) as error:owner_payment(db,link,proof=generated,key='attestation-as-receipt')
    assert error.value.detail['code']=='PAYMENT_EVIDENCE_REQUIRED'


def test_generic_finance_payment_cannot_use_source_invoice_as_owner_payment(monkeypatch,db):
    from app.schemas.finance import Command
    from app.services import finance as f
    source(monkeypatch,snapshot([item()]));sync(db);db.commit();link=db.query(DieselBridgeRepairLink).one()
    with pytest.raises(HTTPException):
        f.append_command(db,1,Command(effective_date='2026-10-20',payload={'kind':'payment','claim_id':link.bill_event_id,
            'amount':'200.00','payer':'owner','evidence_id':link.evidence_id}),'unverified-generic-owner')
    db.rollback()
    assert db.query(DieselBridgeRepairPayment).count()==db.query(RepairReserveLedger).count()==0


def test_generic_credit_or_bill_reversal_cannot_silently_change_source_cost(monkeypatch,db):
    from app.schemas.finance import Command
    from app.services import finance as f
    source(monkeypatch,snapshot([item()]));sync(db);db.commit();link=db.query(DieselBridgeRepairLink).one()
    posting=db.query(FinancePosting).filter_by(event_id=link.bill_event_id).one()
    for payload in [{'kind':'credit_note','claim_id':link.bill_event_id,'amount':'100.00','evidence_id':link.evidence_id,'description':'Unreviewed credit'},
                    {'kind':'reversal','posting_id':posting.id,'reason':'Unreviewed reversal'}]:
        with pytest.raises(HTTPException) as error:f.append_command(db,1,Command(effective_date='2026-10-20',payload=payload),'unreviewed-'+payload['kind'])
        assert error.value.detail['code']=='DBN_INVOICE_REVIEW_REQUIRED'
    assert db.query(Repair).one().cost==Decimal('1000.00')


def test_complete_snapshot_malformed_hash_does_not_overwrite_or_remove_existing(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);db.commit()
    invalid=snapshot([]);invalid['complete']=False;source(monkeypatch,invalid)
    with pytest.raises(HTTPException):sync(db,'partial')
    db.rollback()
    assert db.query(DieselBridgeRepairLink).one().state=='active'


def test_unpaid_invoice_http_tile_state_and_managed_edit_guard(monkeypatch,client,db):
    source(monkeypatch,snapshot([item()]));preview=client.post('/api/v1/accounting/dieselbridge/connections/shop/financial-import/preview',json={},headers={'X-Tenant-ID':'1'})
    assert preview.status_code==200 and preview.json()['executable']
    result=client.post('/api/v1/accounting/dieselbridge/connections/shop/financial-import/sync',json={'expected_plan_digest':preview.json()['plan_digest']},headers={'X-Tenant-ID':'1','Idempotency-Key':'reviewed-import'})
    assert result.status_code==200
    repair=db.query(Repair).one()
    state=client.get(f'/api/v1/accounting/dieselbridge/repairs/{repair.id}/financial-state',headers={'X-Tenant-ID':'1'})
    assert state.status_code==200 and state.json()['payment_status']=='unconfirmed'
    edit=client.put(f'/api/repairs/{repair.id}',json={'cost':'1.00'},headers={'X-Tenant-ID':'1'})
    assert edit.status_code==409


def test_mid_import_failure_rolls_back_normal_cost_and_obligation(monkeypatch,db):
    source(monkeypatch,snapshot([item(),item(2)]));db.commit()
    original=financial.create_repair
    def fail_after_first(*args,**kwargs):
        value=original(*args,**kwargs)
        if value.repair_order_id=='ro-2':raise RuntimeError('Injected after actual writes')
        return value
    monkeypatch.setattr(financial,'create_repair',fail_after_first)
    with pytest.raises(RuntimeError):sync(db)
    db.rollback()
    assert db.query(Repair).count()==db.query(FinanceEvent).count()==db.query(DieselBridgeRepairLink).count()==0


def reconciled_transaction(db,typ='bank',amount='200.00',suffix='1',day='2026-10-20'):
    from app.schemas.finance import Command
    from app.services import finance as f
    account=f.append_command(db,1,Command(effective_date=day,payload={'kind':'account','name':'Verified '+typ+suffix,'account_type':typ}),'account-'+typ+suffix)
    mapping=f.append_command(db,1,Command(effective_date=day,payload={'kind':'csv_mapping','name':'Payment mapping','date_column':'Date','amount_column':'Amount','description_column':'Description','id_column':'ID'}),'mapping-'+typ+suffix)
    import base64
    # Preserve the actual fixture statement bytes before any finance references.
    # The immutable evidence cannot be updated after insertion.
    raw=f'Date,Amount,Description,ID\n{day},-{amount},Repair charge,tx-{suffix}\n'.encode()
    statement_proof=FinanceEvidence(tenant_id=1,sha256=hashlib.sha256(raw).hexdigest(),filename='statement.csv',media_type='text/csv',
        content_base64=base64.b64encode(raw).decode(),source_key='bank-proof-'+typ+suffix,extraction_version='elis-evidence-v1',extracted={})
    db.add(statement_proof);db.flush()
    opening='1000.00' if typ=='bank' else '0.00';closing=f.money(Decimal(opening)-Decimal(amount))
    statement=f.append_command(db,1,Command(effective_date=day,payload={'kind':'statement','account_id':account.id,'mapping_id':mapping.id,
        'evidence_id':statement_proof.id,'start':day,'end':day,'opening':opening,'closing':closing}),'statement-'+typ+suffix)
    return statement.payload['_transactions'][0]['id']


@pytest.mark.parametrize('payer,typ',[('business','bank'),('card','card')])
def test_generic_verified_finance_payment_projects_reserve_once(monkeypatch,db,payer,typ):
    from app.schemas.finance import Command
    from app.services import finance as f
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one()
    tx=reconciled_transaction(db,typ)
    command=Command(effective_date='2026-10-20',payload={'kind':'payment','claim_id':link.bill_event_id,'amount':'200.00','payer':payer,'transaction_id':tx})
    event=f.append_command(db,1,command,'generic-verified-payment')
    assert f.append_command(db,1,command,'generic-verified-payment').id==event.id
    assert db.query(DieselBridgeRepairPayment).count()==1
    assert db.query(RepairReserveLedger).one().amount==Decimal('200.00')
    assert financial.public_state(db,1,link)['recorded_balance_due']=='800.00'
    assert db.query(FinanceEvent).filter_by(kind='bill').count()==1


def test_arbitrary_business_payment_id_is_not_verified(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);db.commit();link=db.query(DieselBridgeRepairLink).one()
    body=VerifiedRepairPayment(expected_revision=link.accepted_revision,amount='200.00',paid_date='2026-10-20',
        payer='business',transaction_id='invented-bank-transfer',note='Unverified transfer number')
    with pytest.raises(HTTPException):financial.record_verified_payment(db,1,link.repair_id,body,'fake-payment')
    db.rollback()
    assert db.query(DieselBridgeRepairPayment).count()==db.query(RepairReserveLedger).count()==0


def test_full_paid_is_sum_of_verified_partials_without_second_expense(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one()
    owner_payment(db,link)
    result=owner_payment(db,link,amount='800.00',key='payment-2')
    assert result['recorded_paid_amount']=='1000.00' and result['recorded_balance_due']=='0.00' and result['payment_status']=='paid'
    assert sum(x.amount for x in db.query(RepairReserveLedger).filter_by(entry_type='withdrawal'))==Decimal('1000.00')
    assert db.query(FinanceEvent).filter_by(kind='bill').count()==1
    assert db.query(Repair).one().cost==Decimal('1000.00')


def test_reviewed_change_blocks_new_payments_and_source_pdf_access_removal(monkeypatch,db,client):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one()
    source(monkeypatch,snapshot([item(total='1200.00')]));sync(db,'changed')
    with pytest.raises(HTTPException) as error:owner_payment(db,link)
    assert error.value.detail['code']=='REVIEW_REQUIRED'
    source(monkeypatch,snapshot([item(authorization='attribution_required')]));sync(db,'removed');db.commit()
    pdf=client.get(f'/api/v1/accounting/dieselbridge/repairs/{link.repair_id}/source-pdf',headers={'X-Tenant-ID':'1'})
    assert pdf.status_code==404
    assert db.query(Repair).one().cost==Decimal('1000.00')


def test_pure_preview_blocked_initial_batch_cannot_partially_import(monkeypatch,client,db):
    source(monkeypatch,snapshot([item(),item(2,authorization='attribution_required')]))
    preview=client.post('/api/v1/accounting/dieselbridge/connections/shop/financial-import/preview',json={},headers={'X-Tenant-ID':'1'})
    assert preview.status_code==200 and not preview.json()['executable']
    assert db.query(Repair).count()==0
    response=client.post('/api/v1/accounting/dieselbridge/connections/shop/financial-import/sync',json={'expected_plan_digest':preview.json()['plan_digest']},headers={'X-Tenant-ID':'1','Idempotency-Key':'all-orders'})
    assert response.status_code==409 and db.query(Repair).count()==0


def test_unconfirmed_trailer_cost_and_duplicate_vin_are_reviewed(monkeypatch,db):
    source(monkeypatch,snapshot([item(description='Replace six Trailer Tire items')]))
    assert sync(db)['blocked']==1 and db.query(Repair).count()==0
    db.add(Truck(tenant_id=1,name='Duplicate VIN',vehicle_type='truck',vin='VIN609'));db.flush()
    source(monkeypatch,snapshot([item()]))
    assert sync(db,'duplicate-vin')['blocked']==1 and db.query(Repair).count()==0


def test_completion_missing_uses_evidenced_issue_not_unknown_import_date(monkeypatch,db):
    source(monkeypatch,snapshot([item(work_completed_at=None,service_date=None)]))
    sync(db);assert db.query(Repair).one().repair_date==date(2026,10,19)
    other=item(2,work_completed_at=None,service_date=None)
    other['invoice']['invoice_date']=None;other['invoice']['invoice_date_basis']='unknown'
    other['invoice']['revision']=digest({k:v for k,v in other['invoice'].items() if k!='revision'})
    other['revision']=digest({k:v for k,v in other.items() if k not in ('revision','settlement')})
    source(monkeypatch,snapshot([other]));result=sync(db,'unknown-issue',repair_order_ids=['ro-2'])
    assert result['blocked']==1 and db.query(Repair).count()==1


def test_explicit_unpaid_revision_changes_one_cost_and_payable_without_reserve(monkeypatch,db,client):
    from app.services import finance as f
    source(monkeypatch,snapshot([item()]));sync(db);db.commit();link=db.query(DieselBridgeRepairLink).one()
    accepted=link.accepted_revision;source(monkeypatch,snapshot([item(total='1200.00')]))
    endpoint=f'/api/v1/accounting/dieselbridge/repairs/{link.repair_id}/source-review'
    preview=client.post(endpoint+'/preview',json={'expected_revision':accepted},headers={'X-Tenant-ID':'1'})
    assert preview.status_code==200 and preview.json()['can_apply'] and preview.json()['after']['cost']=='1200.00'
    assert db.query(Repair).one().cost==Decimal('1000.00')
    request={'expected_revision':accepted,'expected_review_digest':preview.json()['review_digest'],'note':'Reviewed replacement invoice and amount'}
    result=client.post(endpoint+'/apply',json=request,headers={'X-Tenant-ID':'1','Idempotency-Key':'review-1'})
    assert result.status_code==200,result.json()
    assert client.post(endpoint+'/apply',json=request,headers={'X-Tenant-ID':'1','Idempotency-Key':'review-1'}).json()==result.json()
    assert db.query(Repair).one().cost==Decimal('1200.00')
    assert db.query(RepairReserveLedger).count()==0
    report=f.ledger_report(db,1,date.min,date.max)
    assert report['income_statement']['net_income']=='-1200.00'
    assert len([e for e in f.state(db,1,date.max)['events'] if e.kind=='bill' and e.id in f.state(db,1,date.max)['active_event_ids']])==1
    from app.services.repair_history import repair_history
    reviewed=repair_history(db,1,date.today())['rows'][0]
    assert reviewed['source_totals']==['1200.00'] and 'invoice_amount_difference' not in reviewed['issues']


def cancellation_source(monkeypatch,*,cancelled=True):
    async def request(self,path,params=None):
        if path=='repair-orders/financial':return httpx.Response(200,json=snapshot([]))
        assert path=='invoices'
        old={'shop_id':'shop-1','invoice_id':'invoice-1','invoice_number':'INV-1','effective_updated_at':'2026-10-21T12:00:00+00:00',
            'currency':'USD','status':'cancelled' if cancelled else 'paid','total_amount':'1000.00','invoice_date':'2026-10-19','vin':'VIN609',
            'voided_at':'2026-10-21T12:00:00+00:00' if cancelled else None}
        return httpx.Response(200,json={'watermark':params['updated_before'],'items':[old],'next_cursor':None})
    monkeypatch.setattr(d.SourceClient,'request',request)


def test_authorized_cancellation_is_reversible_archive_not_delete(monkeypatch,db,client):
    from app.services import finance as f
    source(monkeypatch,snapshot([item()]));sync(db);db.commit();link=db.query(DieselBridgeRepairLink).one()
    accepted=link.accepted_revision;repair_id=link.repair_id;cancellation_source(monkeypatch)
    base=f'/api/v1/accounting/dieselbridge/repairs/{repair_id}'
    preview=client.post(base+'/source-review/preview',json={'expected_revision':accepted},headers={'X-Tenant-ID':'1'})
    assert preview.status_code==200 and preview.json()['action']=='cancel_unpaid_invoice' and preview.json()['can_apply']
    body={'expected_revision':accepted,'expected_review_digest':preview.json()['review_digest'],'note':'Verified source cancellation'}
    first=client.post(base+'/source-review/apply',json=body,headers={'X-Tenant-ID':'1','Idempotency-Key':'cancel-review'})
    assert first.status_code==200,first.json()
    assert client.post(base+'/source-review/apply',json=body,headers={'X-Tenant-ID':'1','Idempotency-Key':'cancel-review'}).json()==first.json()
    assert db.query(Repair).count()==0
    original=db.query(Repair).execution_options(include_archived_repairs=True).one()
    assert original.cost==Decimal('1000.00') and original.archived_at is not None
    assert f.ledger_report(db,1,date.min,date.max)['income_statement']['net_income']=='0.00'
    state=client.get(base+'/financial-state',headers={'X-Tenant-ID':'1'})
    assert state.status_code==200 and state.json()['state']=='cancelled'
    assert state.json()['booked_cost']=='0.00' and state.json()['source_invoice_total']=='1000.00' and state.json()['recorded_balance_due']=='0.00'


def test_absence_without_authorized_cancellation_cannot_erase_cost(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one();cancellation_source(monkeypatch,cancelled=False)
    preview,_,_,_=asyncio.run(financial.review_preview(db,1,link.repair_id,link.accepted_revision))
    assert not preview['can_apply'] and 'AUTHORIZED_CANCELLATION_OR_CURRENT_INVOICE_REQUIRED' in preview['blockers']
    assert db.query(Repair).one().cost==Decimal('1000.00')


def test_source_review_with_active_verified_payments_requires_correction(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one();owner_payment(db,link)
    source(monkeypatch,snapshot([item(total='1200.00')]))
    preview,_,_,_=asyncio.run(financial.review_preview(db,1,link.repair_id,link.accepted_revision))
    assert not preview['can_apply'] and 'PAYMENT_CORRECTION_REQUIRED' in preview['blockers']
    assert db.query(Repair).one().cost==Decimal('1000.00')


def test_access_restoration_requires_explicit_matching_review(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one();revision=link.accepted_revision
    source(monkeypatch,snapshot([item(authorization='attribution_required')]));sync(db,'removed')
    assert link.state=='access_removed'
    source(monkeypatch,snapshot([item()]))
    preview,_,_,_=asyncio.run(financial.review_preview(db,1,link.repair_id,revision))
    assert preview['action']=='no_change' and preview['can_apply']
    body=SourceReviewApply(expected_revision=revision,expected_review_digest=preview['review_digest'],note='Reverified source authorization restored')
    asyncio.run(financial.apply_source_review(db,1,link.repair_id,body,'restore-access'))
    assert link.state=='active' and db.query(FinanceEvent).count()==1


def test_stale_source_review_digest_cannot_apply_new_amount(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one();revision=link.accepted_revision
    source(monkeypatch,snapshot([item(total='1200.00')]))
    preview,_,_,_=asyncio.run(financial.review_preview(db,1,link.repair_id,revision))
    source(monkeypatch,snapshot([item(total='1400.00')]))
    body=SourceReviewApply(expected_revision=revision,expected_review_digest=preview['review_digest'],note='Previously reviewed amount')
    with pytest.raises(HTTPException) as error:asyncio.run(financial.apply_source_review(db,1,link.repair_id,body,'stale-review'))
    assert error.value.detail['code']=='STALE_SOURCE_REVIEW' and db.query(Repair).one().cost==Decimal('1000.00')


def test_cancelled_archive_does_not_poison_next_complete_financial_sync(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one();revision=link.accepted_revision
    cancellation_source(monkeypatch)
    preview,_,_,_=asyncio.run(financial.review_preview(db,1,link.repair_id,revision))
    body=SourceReviewApply(expected_revision=revision,expected_review_digest=preview['review_digest'],note='Approved authorized cancellation')
    asyncio.run(financial.apply_source_review(db,1,link.repair_id,body,'cancel-old'));db.commit()
    source(monkeypatch,snapshot([item(2)]))
    result=sync(db,'new-ro-after-cancel')
    assert result['created']==1 and result['unchanged']==1
    assert db.query(Repair).count()==1 and db.query(Repair).one().invoice_number=='INV-2'
    archived=db.query(Repair).execution_options(include_archived_repairs=True).filter_by(id=link.repair_id).one()
    assert archived.archived_at and link.state=='cancelled'
    source(monkeypatch,snapshot([item(),item(2)]))
    result=sync(db,'old-reappeared')
    assert result['review_required']==1 and result['unchanged']==1 and db.query(Repair).count()==1
    assert financial.public_state(db,1,link)['booked_cost']=='0.00'


def test_period_closed_after_review_stales_plan_and_preserves_every_projection(monkeypatch,db,client):
    source(monkeypatch,snapshot([item()]));sync(db);db.commit();link=db.query(DieselBridgeRepairLink).one();revision=link.accepted_revision
    source(monkeypatch,snapshot([item(total='1200.00')]))
    preview,_,_,_=asyncio.run(financial.review_preview(db,1,link.repair_id,revision))
    assert preview['can_apply']
    db.add(FinanceEvent(tenant_id=1,key='fixture-period-close',digest='a'*64,kind='close_period',effective_date=date(2026,10,30),payload={'start':'2026-10-01','end':'2026-10-31'}));db.commit()
    latest,_,_,_=asyncio.run(financial.review_preview(db,1,link.repair_id,revision))
    assert not latest['can_apply'] and 'PERIOD_CLOSED' in latest['blockers']
    response=client.post(f'/api/v1/accounting/dieselbridge/repairs/{link.repair_id}/source-review/apply',
        json={'expected_revision':revision,'expected_review_digest':preview['review_digest'],'note':'Previously reviewed before period closed'},headers={'X-Tenant-ID':'1','Idempotency-Key':'closed-period-review'})
    assert response.status_code==409
    assert db.query(Repair).one().cost==Decimal('1000.00') and db.query(FinanceEvidence).count()==1
    assert db.query(FinanceEvent).filter_by(kind='bill').count()==1 and db.query(FinanceEvent).filter_by(kind='reversal').count()==0


def test_scoped_financial_state_and_payment_hide_foreign_repair(monkeypatch,db,client):
    from app.models.tenant import Tenant
    source(monkeypatch,snapshot([item()]));sync(db);db.add(Tenant(id=2,name='Other Business',business_type='logistics'));db.commit()
    link=db.query(DieselBridgeRepairLink).one();monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS','1,2')
    foreign=client.get(f'/api/v1/accounting/dieselbridge/repairs/{link.repair_id}/financial-state',headers={'X-Tenant-ID':'2'})
    absent=client.get('/api/v1/accounting/dieselbridge/repairs/999999/financial-state',headers={'X-Tenant-ID':'2'})
    assert foreign.status_code==absent.status_code==404
    payment=client.post(f'/api/v1/accounting/dieselbridge/repairs/{link.repair_id}/verified-payments',json={'expected_revision':link.accepted_revision,'amount':'200.00','paid_date':'2026-10-20','payer':'owner','owner_payment_confirmed':True,'note':'Foreign repair payment'},headers={'X-Tenant-ID':'2','Idempotency-Key':'foreign-payment'})
    assert payment.status_code==404 and db.query(DieselBridgeRepairPayment).count()==0


def test_pending_pdf_selects_fresh_authorized_current_invoice_not_client_id(monkeypatch,db,client):
    source(monkeypatch,snapshot([item()]));sync(db);db.commit();link=db.query(DieselBridgeRepairLink).one()
    pending=item(total='1200.00');pending['invoice']['invoice_id']='replacement-invoice';pending['invoice']['revision']=digest({k:v for k,v in pending['invoice'].items() if k!='revision'});pending['revision']=digest({k:v for k,v in pending.items() if k not in ('revision','settlement')})
    source(monkeypatch,snapshot([pending]));seen=[]
    async def pdf(self,invoice_id):seen.append(invoice_id);return b'%PDF-1.4 fixture'
    monkeypatch.setattr(d.SourceClient,'pdf',pdf)
    response=client.get(f'/api/v1/accounting/dieselbridge/repairs/{link.repair_id}/source-review/pdf',headers={'X-Tenant-ID':'1'})
    assert response.status_code==200 and seen==['replacement-invoice']
    source(monkeypatch,snapshot([item(authorization='attribution_required')]))
    response=client.get(f'/api/v1/accounting/dieselbridge/repairs/{link.repair_id}/source-review/pdf',headers={'X-Tenant-ID':'1'})
    assert response.status_code==404 and seen==['replacement-invoice']


def legacy_invoice(db,*,repair_id=None):
    from app.models.dieselbridge import DieselBridgeInvoice
    row=DieselBridgeInvoice(tenant_id=1,source_system='dieselbridge',shop_id='shop-1',bill_to_id='customer-1',
        invoice_id='older-source-invoice',revision='2026-10-19T00:00:00+00:00',payload={'repair_order_id':'ro-1','invoice_id':'older-source-invoice',
        'invoice_number':'OLDER-INVOICE','invoice_date':'2026-10-01','total_amount':'1000.00','vin':'VIN609'},
        truck_id=1,repair_id=repair_id,state='accepted' if repair_id else 'review_required',review_reason='cost_treatment_required',
        accepted_revision='2026-10-19T00:00:00+00:00' if repair_id else None)
    db.add(row);db.flush();return row


def test_legacy_accepted_invoice_same_ro_blocks_new_expense_despite_new_number(monkeypatch,db):
    old=Repair(truck_id=1,repair_date=date(2026,10,1),cost=Decimal('1000.00'),invoice_number='OLDER-INVOICE',paid_from_reserve=False)
    db.add(old);db.flush();legacy_invoice(db,repair_id=old.id)
    source(monkeypatch,snapshot([item()]));result=sync(db)
    assert result['blocked']==1 and db.query(Repair).count()==1 and db.query(DieselBridgeRepairLink).count()==0


def test_legacy_accept_cannot_duplicate_new_canonical_ro(monkeypatch,db):
    source(monkeypatch,snapshot([item()]));sync(db);old=legacy_invoice(db)
    with pytest.raises(HTTPException) as error:d.accept(db,1,old.id,old.revision,'Review old invoice')
    assert error.value.detail['code']=='EXISTING_REPAIR_SOURCE_REVIEW'
    assert db.query(Repair).count()==1


def test_generic_future_bank_payment_is_rejected_and_fully_rolled_back(monkeypatch,db):
    from app.schemas.finance import Command
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one()
    future=(date.today()+timedelta(days=2)).isoformat()
    tx=reconciled_transaction(db,day=future,suffix='future');db.commit()
    baseline_events=db.query(FinanceEvent).count();baseline_postings=db.query(FinancePosting).count()
    with pytest.raises(HTTPException) as error:
        f.append_command(db,1,Command(effective_date=future,payload={'kind':'payment','claim_id':link.bill_event_id,
            'amount':'200.00','payer':'business','transaction_id':tx}),'generic-future-payment')
    assert error.value.detail['code']=='INVALID_PAYMENT_DATE'
    db.rollback()
    assert db.query(FinanceEvent).count()==baseline_events and db.query(FinancePosting).count()==baseline_postings
    assert db.query(FinanceEvent).filter_by(kind='payment').count()==0
    assert db.query(DieselBridgeRepairPayment).count()==db.query(RepairReserveLedger).count()==0


def test_generic_future_payment_reversal_is_rejected_and_fully_rolled_back(monkeypatch,db):
    from app.schemas.finance import Command
    source(monkeypatch,snapshot([item()]));sync(db);link=db.query(DieselBridgeRepairLink).one();owner_payment(db,link);db.commit()
    payment=db.query(DieselBridgeRepairPayment).one()
    posting=db.query(FinancePosting).filter_by(event_id=payment.event_id).one()
    baseline_events=db.query(FinanceEvent).count();baseline_postings=db.query(FinancePosting).count()
    future=(date.today()+timedelta(days=2)).isoformat()
    with pytest.raises(HTTPException) as error:
        f.append_command(db,1,Command(effective_date=future,payload={'kind':'reversal','posting_id':posting.id,'reason':'Future-dated correction not yet occurred'}),'generic-future-reversal')
    assert error.value.detail['code']=='INVALID_PAYMENT_DATE'
    db.rollback()
    assert db.query(FinanceEvent).count()==baseline_events and db.query(FinancePosting).count()==baseline_postings
    assert db.query(FinanceEvent).filter_by(kind='reversal').count()==0
    assert db.query(DieselBridgeRepairPayment).one().reversal_event_id is None
    assert db.query(RepairReserveLedger).filter_by(entry_type='withdrawal').count()==1
    assert db.query(RepairReserveLedger).filter_by(entry_type='withdrawal_reversal').count()==0
