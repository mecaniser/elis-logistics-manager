"""Scoped financial RO import and verified-payment projections. Helpers flush only.

Invoices recognize cost/payable; only existing verified Finance payment commands
spend reserves. No helper calls the legacy repair form's assumed-cash workflow.
"""
import base64
import hashlib
import json
import os
import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from app.models.dieselbridge import DieselBridgeRepairLink as Link, DieselBridgeRepairPayment as Payment, DieselBridgeFinancialOperation as Operation
from app.models.finance import FinanceEvidence, FinanceEvent, FinancePosting
from app.models.repair import Repair
from app.models.repair_reserve_ledger import RepairReserveLedger
from app.models.truck import Truck
from app.schemas.finance import Command
from app.services import dieselbridge as d
from app.services import finance as f
from app.utils.reserve_regime import RESERVE_REGIME_START_DATE
from app.services import dieselbridge_settlement as settlement
from app.services import dieselbridge_equipment as equipment

VERSION = 'db094-repair-financial-v2'
SNAPSHOT_FIELDS = {'version','shop_id','customer_id','complete','count','snapshot_id','items'}
ROW_FIELDS = {'repair_order_id','order_number','vehicle_id','vin','unit_number','description','work_completed_at','service_date','authorization','invoice','settlement','revision'}
INVOICE_FIELDS = {'invoice_id','revision','invoice_number','status','invoice_date','invoice_date_basis','currency','total_amount','line_items','pdf_sha256','breakdown'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def financial_enabled():
    return os.getenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','').lower() in ('1','true')


def require_enabled():
    if not financial_enabled():
        f.fail('Financial import is disabled pending release and reconciliation approval.','FEATURE_DISABLED',503)


def protocol():
    f.fail('Invalid complete financial manifest. Existing financial records were preserved.','SOURCE_PROTOCOL_ERROR',502)


def validate_manifest(value,config):
    try:
        if not isinstance(value,dict) or set(value)!=SNAPSHOT_FIELDS or value['version']!=VERSION:
            protocol()
        if (value['shop_id'],value['customer_id'])!=(str(config['shop_id']),str(config['bill_to_id'])):
            protocol()
        if value['complete'] is not True or type(value['count']) is not int or not isinstance(value['items'],list) or value['count']!=len(value['items']) or value['count']>1000:
            protocol()
        seen=set(); invoices=set(); attempt_ids=set(); payment_count=0
        for row in value['items']:
            if not isinstance(row,dict) or set(row)!=ROW_FIELDS:protocol()
            for name in ('repair_order_id','order_number','vehicle_id'):
                if not isinstance(row[name],str) or not row[name].strip() or len(row[name])>100:protocol()
            if len(row['repair_order_id'])>80:protocol()
            if row['repair_order_id'] in seen:protocol()
            seen.add(row['repair_order_id'])
            for name,limit in (('vin',100),('unit_number',100),('description',50000)):
                if row[name] is not None and (not isinstance(row[name],str) or len(row[name])>limit):protocol()
            if row['work_completed_at'] is not None:
                completed=d.timestamp(row['work_completed_at']).date().isoformat()
                if completed!=row['service_date']:protocol()
            if row['service_date'] is not None:date.fromisoformat(row['service_date'])
            if row['authorization'] not in ('authorized','attribution_required','not_finalized','unavailable'):protocol()
            inv=row['invoice']
            if row['authorization']!='authorized':
                if inv is not None or row['settlement'] is not None:protocol()
            else:
                if not isinstance(inv,dict) or set(inv)!=INVOICE_FIELDS:protocol()
                for name in ('invoice_id','invoice_number'):
                    if not isinstance(inv[name],str) or not inv[name].strip() or len(inv[name])>100:protocol()
                if len(inv['invoice_id'])>80 or len(inv['invoice_number'])>50:protocol()
                if inv['invoice_id'] in invoices:protocol()
                invoices.add(inv['invoice_id'])
                if inv['status']!='current_finalized' or inv['currency']!='USD':protocol()
                if not isinstance(inv['total_amount'],str) or not re.fullmatch(r'(0|[1-9][0-9]{0,7})\.[0-9]{2}',inv['total_amount']):protocol()
                amount=Decimal(inv['total_amount'])
                if not amount.is_finite() or amount<0 or amount>=Decimal('100000000') or amount.as_tuple().exponent < -2:protocol()
                if inv['invoice_date_basis'] not in ('native_issue_timestamp','preserved_issue_date','unknown'):protocol()
                if inv['invoice_date'] is not None:date.fromisoformat(inv['invoice_date'])
                if inv['invoice_date_basis']=='unknown' and inv['invoice_date'] is not None:protocol()
                if inv['line_items'] is not None and not isinstance(inv['line_items'],dict):protocol()
                if inv['pdf_sha256'] is not None and not re.fullmatch('[0-9a-f]{64}',inv['pdf_sha256']):protocol()
                settlement.validate(inv,row['settlement'])
                source_payments=(row['settlement'] or {}).get('payments',[])
                payment_count+=len(source_payments)
                if payment_count>10000:protocol()
                for source_payment in source_payments:
                    if source_payment['attempt_id'] in attempt_ids:protocol()
                    attempt_ids.add(source_payment['attempt_id'])
                if inv['revision']!=digest({k:v for k,v in inv.items() if k!='revision'}):protocol()
            if row['revision']!=digest({k:v for k,v in row.items() if k not in ('revision','settlement')}):protocol()
        if value['snapshot_id']!=digest({k:value[k] for k in ('version','shop_id','customer_id','items')}):protocol()
    except (KeyError,TypeError,ValueError,InvalidOperation):protocol()
    return value


async def manifest(config):
    response=await d.SourceClient(config).request('repair-orders/financial')
    try:return validate_manifest(response.json(),config)
    except (ValueError,TypeError):protocol()


def occurrence(row):
    if row['work_completed_at']:
        return d.timestamp(row['work_completed_at']).date()
    invoice=row.get('invoice')
    if invoice and invoice['invoice_date_basis']!='unknown' and invoice['invoice_date']:
        return date.fromisoformat(invoice['invoice_date'])
    return None


def resolved_occurrence(db,tenant,config,row):
    """Only explicit reviews override source occurrence; narrative dates remain notes."""
    if not row:return None,None,None
    from app.models.dieselbridge_reconciliation import DieselBridgeReconciliationNote as Note
    decision=db.query(Note).filter_by(tenant_id=tenant,slug=config['slug'],shop_id=str(config['shop_id']),
        customer_id=str(config['bill_to_id']),repair_order_id=row['repair_order_id']).filter(Note.date_treatment!='note_only').order_by(Note.id.desc()).first()
    if not decision:return occurrence(row),None,None
    from app.services.dieselbridge_reconciliation import public
    proof=public(decision)
    if decision.source_revision!=row['revision']:return None,proof,'date_decision_source_changed'
    return (decision.confirmed_service_date if decision.date_treatment=='confirmed_service_date' else occurrence(row)),proof,None


def work_text(row):
    inv=row.get('invoice') or {}; lines=inv.get('line_items') or {}
    text=[row.get('description') or '']
    for kind,field in (('labor','description'),('parts','name')):
        for entry in lines.get(kind,[]) or []:
            if isinstance(entry,dict) and isinstance(entry.get(field),str):text.append(entry[field])
    return '\n'.join(text).strip()


def category(row):
    text=work_text(row).lower()
    if any(x in text for x in ('pm service','full pm','preventive maintenance','oil change')):return 'maintenance'
    if any(x in text for x in ('transmission','clutch')):return 'transmission'
    if any(x in text for x in ('brake','rotor')):return 'brakes'
    if any(x in text for x in ('tire','tyre')):return 'tires'
    if any(x in text for x in ('battery','batteries','blower','wiper')):return 'electrical'
    if any(x in text for x in ('nox','def ','dpf','coolant','engine')):return 'engine'
    return 'other'


def needs_asset_review(row):
    # A tractor VIN must not silently assign a trailer-specific invoice to it.
    return bool(re.search(r'\btrailer\b',work_text(row),re.I))


def scoped_link(db,tenant,repair_id):
    link=db.query(Link).filter_by(tenant_id=tenant,repair_id=repair_id).first()
    if not link or not db.query(Repair).join(Truck).filter(Repair.id==repair_id,Truck.tenant_id==tenant).execution_options(include_archived_repairs=True).first():
        f.fail('Repair not found.','RESOURCE_NOT_FOUND',404)
    return link


def public_state(db,tenant,link):
    from app.services.dieselbridge_reconciliation import for_link
    from app.services.dieselbridge_replacements import audit_summaries
    repair=db.query(Repair).join(Truck).filter(Repair.id==link.repair_id,Truck.tenant_id==tenant).execution_options(include_archived_repairs=True).first()
    if not repair:f.fail('Repair not found.','RESOURCE_NOT_FOUND',404)
    rows=db.query(Payment).filter_by(tenant_id=tenant,link_id=link.id).order_by(Payment.id).all()
    paid=sum((r.amount for r in rows if not r.reversal_event_id),f.ZERO)
    total=f.ZERO if link.state=='cancelled' or repair.archived_at else f.D(repair.cost)
    payload=link.accepted_payload;inv=payload['invoice']
    source_row={**payload,'settlement':link.source_settlement_payload}
    visible_settlement=link.source_settlement_payload if link.state!='access_removed' else None
    observed=settlement.projection(source_row) if inv.get('breakdown') and link.state!='access_removed' else {'amount':None,'confirmed':None,'balance':None}
    source_claims=[{'source_attempt_id':p.source_attempt_id,'source_attempt_revision':p.source_attempt_revision,'payment_id':p.id,'reversed':bool(p.reversal_event_id)} for p in rows if p.source_attempt_id]
    allocation=equipment.latest(db,tenant,{'slug':link.slug,'shop_id':link.shop_id,'bill_to_id':link.customer_id},link.repair_order_id)
    return {'link_id':link.id,'connection_slug':link.slug,'repair_order_id':link.repair_order_id,
        'equipment_allocation':equipment.public(allocation) if allocation else None,'cost_asset_id':repair.truck_id,
        'temporary_replacements':audit_summaries(db,tenant,link),
        'order_number':payload['order_number'],'invoice_id':link.accepted_invoice_id,
        'invoice_number':inv['invoice_number'],'revision':link.accepted_revision,'state':link.state,
        'review_reason':link.review_reason,'source_status':'cancelled' if link.state=='cancelled' else 'unavailable' if link.state=='access_removed' else 'finalized',
        'invoice_total':f.money(total),'source_invoice_total':inv['total_amount'],'booked_cost':f.money(total),'recorded_paid_amount':f.money(paid),
        'recorded_balance_due':f.money(total-paid),'payment_status':'unconfirmed' if paid==0 else 'paid' if paid==total else 'partial',
        'bill_event_id':link.bill_event_id,'payments':[{'id':p.id,'event_id':p.event_id,'amount':f.money(p.amount),
            'paid_date':p.paid_date.isoformat(),'payer':p.payer,'reversed':bool(p.reversal_event_id),
            'reserve_withdrawal_id':p.reserve_withdrawal_id,'source_attempt_id':p.source_attempt_id,'source_attempt_revision':p.source_attempt_revision} for p in rows],
        'source_settlement':visible_settlement,'source_claims':source_claims,
        'source_payment_review_required':bool(link.source_payment_review_reasons),'source_payment_review_reasons':link.source_payment_review_reasons or [],
        'source_quoted_card_fee':inv.get('breakdown',{}).get('service_fee_amount'),
        'source_applied_card_fee':f.money(sum((Decimal(p['applied_card_fee_amount'])+Decimal(p['applied_card_fee_tax_amount']) for p in (visible_settlement or {}).get('payments',[]) if p['state']=='confirmed'),f.ZERO)) if link.state!='access_removed' else None,
        'source_obligation_amount':observed['amount'],'source_confirmed_amount':observed['confirmed'],'source_recorded_balance':observed['balance'],
        'source_pdf_url':f'/api/v1/accounting/dieselbridge/repairs/{repair.id}/source-pdf' if link.state!='access_removed' else None,
        **for_link(db,tenant,link)}


def source_claim_issues(db,tenant,link,row):
    observed={p['attempt_id']:p for p in (row.get('settlement') or {}).get('payments',[])}
    issues=[]
    for payment in db.query(Payment).filter_by(tenant_id=tenant,link_id=link.id,reversal_event_id=None).all():
        if not payment.source_attempt_id:continue
        current=observed.get(payment.source_attempt_id)
        if not current or current['state']!='confirmed' or current['revision']!=payment.source_attempt_revision:
            issues.append('source_payment_changed')
        elif current['gross_received_amount'] is None or Decimal(current['gross_received_amount'])!=payment.amount:
            issues.append('source_payment_amount_changed')
    return sorted(set(issues))


def preserve_settlement_observation(db,tenant,link,row):
    raw=json.dumps({'shop_id':link.shop_id,'customer_id':link.customer_id,'repair_order_id':link.repair_order_id,'invoice_id':row['invoice']['invoice_id'],'settlement':row.get('settlement')},sort_keys=True).encode()
    sha=hashlib.sha256(raw).hexdigest()
    if not db.query(FinanceEvidence).filter_by(tenant_id=tenant,sha256=sha).first():
        db.add(FinanceEvidence(tenant_id=tenant,sha256=sha,filename='dbn-settlement-observation.json',media_type='application/json',content_base64=base64.b64encode(raw).decode(),source_key='dbn-settlement:'+str(link.id),extraction_version='db094-settlement-observation-v2',extracted={'source':json.loads(raw),'payment_basis':'source_observation_only'}))
        db.flush()


def source_claim_request(body):
    if bool(body.source_attempt_id)!=bool(body.source_attempt_revision):
        f.fail('Source attempt identity and revision are required together.','SOURCE_PAYMENT_REFERENCE_REQUIRED',422)
    return {'attempt_id':body.source_attempt_id,'revision':body.source_attempt_revision} if body.source_attempt_id else None


def validate_source_claim(db,tenant,link,claim,amount,paid_date,payer):
    # The stored observation is never sufficient authority to post a payment.
    # This function also runs in the shared Finance projection, rejecting forged
    # or reused evidence supplied through another Finance entry point.
    import asyncio
    config=d.config(tenant,link.slug);d.connection(db,tenant,config)
    if (link.shop_id,link.customer_id)!=(str(config['shop_id']),str(config['bill_to_id'])):
        f.fail('Connection scope changed.','CONNECTION_SCOPE_CHANGED')
    value=asyncio.run(manifest(config))
    row=next((r for r in value['items'] if r['repair_order_id']==link.repair_order_id),None)
    if not row or row['authorization']!='authorized':f.fail('Source payment is unavailable.','SOURCE_PAYMENT_REVIEW_REQUIRED')
    if row['invoice']['invoice_id']!=link.accepted_invoice_id or row['invoice']['revision']!=link.accepted_revision or row['revision']!=link.accepted_payload['revision']:
        f.fail('Source invoice changed. Refresh and review first.','STALE_INVOICE')
    projected=settlement.projection(row)
    repair=db.query(Repair).filter_by(id=link.repair_id).one()
    if projected['reasons'] or source_claim_issues(db,tenant,link,row) or projected['amount'] is None or Decimal(projected['amount'])!=Decimal(repair.cost):
        f.fail('Source settlement needs review before payment verification.','SOURCE_PAYMENT_REVIEW_REQUIRED')
    attempt=next((p for p in (row.get('settlement') or {}).get('payments',[]) if p['attempt_id']==claim.get('attempt_id')),None)
    if not attempt or attempt['revision']!=claim.get('revision'):
        f.fail('Source payment changed. Refresh before recording it.','STALE_SOURCE_PAYMENT')
    if settlement.receipt_amount(attempt)!=f.D(amount):
        f.fail('Record exactly the whole confirmed source receipt; split claims need review.','SOURCE_PAYMENT_AMOUNT_MISMATCH')
    if attempt['actual_paid_date'] and attempt['actual_paid_date']!=paid_date.isoformat():
        f.fail('Use the evidenced actual source payment date.','INVALID_PAYMENT_DATE',422)
    if payer!='owner' and payer!={'cash':'cash','card':'card','zelle':'business','ach':'business','check':'business','fleet_payment':'business'}[attempt['rail']]:
        f.fail('Funding account must match the recorded source payment rail, or verify personal funding.','SOURCE_PAYMENT_FUNDING_MISMATCH')
    active=db.query(Payment).filter_by(tenant_id=tenant,source_shop_id=link.shop_id,source_attempt_id=attempt['attempt_id'],reversal_event_id=None).first()
    if active:f.fail('This source payment already has an active verified allocation.','DUPLICATE_SOURCE_PAYMENT')
    return row,attempt


def build_preview(db,tenant,config,value,selection=None):
    if selection is not None and (not selection or len(set(selection))!=len(selection)):
        f.fail('Choose each repair order only once.','INVALID_SELECTION',422)
    available={r['repair_order_id']:r for r in value['items']}
    links=db.query(Link).filter_by(tenant_id=tenant,shop_id=str(config['shop_id'])).all()
    old={r.repair_order_id:r for r in links}
    from app.models.dieselbridge import DieselBridgeInvoice
    legacy=db.query(DieselBridgeInvoice).filter(DieselBridgeInvoice.tenant_id==tenant,
        DieselBridgeInvoice.shop_id==str(config['shop_id']),DieselBridgeInvoice.repair_id.is_not(None)).all()
    legacy_ro_ids={i.payload.get('repair_order_id') for i in legacy}
    legacy_invoice_ids={i.invoice_id for i in legacy}
    if any(l.customer_id!=str(config['bill_to_id']) for l in links):
        f.fail('The financial connection customer scope changed.','CONNECTION_SCOPE_CHANGED')
    selected=sorted(selection if selection is not None else set(available)|set(old))
    rows=[];local=[]
    for rid in selected:
        row=available.get(rid);link=old.get(rid);inv=row.get('invoice') if row else None
        repair=db.query(Repair).filter_by(id=link.repair_id).execution_options(include_archived_repairs=True).first() if link else None
        if link and not repair:f.fail('Accepted source repair is unavailable. Review its archive.','REPAIR_ARCHIVE_REVIEW')
        blockers=[];truck_id,reason,allocation=equipment.resolve(db,tenant,config,row)
        when,date_decision,date_issue=resolved_occurrence(db,tenant,config,row)
        projected=settlement.projection(row) if inv else None
        if link and repair.archived_at:
            if row and row['authorization']=='authorized':action='review_required';blockers=['archived_repair_restoration_required']
            else:action='unchanged'
        elif link:
            if not row or row['authorization']!='authorized':action='review_required';blockers=['source_access_or_invoice_unavailable']
            elif date_issue:action='review_required';blockers=[date_issue]
            elif when!=repair.repair_date:action='review_required';blockers=['repair_date_changed']
            elif truck_id!=repair.truck_id:action='review_required';blockers=['truck_identity_changed']
            elif projected['reasons']:action='review_required';blockers=projected['reasons']
            elif Decimal(projected['amount'])!=Decimal(repair.cost):action='review_required';blockers=['source_settlement_cost_changed']
            elif source_claim_issues(db,tenant,link,row):action='review_required';blockers=['source_payment_changed']
            elif inv['invoice_id']!=link.accepted_invoice_id or inv['revision']!=link.accepted_revision or row['revision']!=link.accepted_payload['revision']:
                action='review_required';blockers=['source_invoice_changed']
            else:action='unchanged'
        else:
            if not row:blockers.append('source_order_unavailable')
            elif row['authorization']!='authorized':blockers.append('historical_attribution_required' if row['authorization']=='attribution_required' else 'current_finalized_invoice_required')
            if reason!='cost_treatment_required':blockers.append(reason)
            if when is None:blockers.append(date_issue or 'date_evidence_required')
            asset=db.query(Truck).filter_by(id=truck_id,tenant_id=tenant).first() if truck_id else None
            if row and needs_asset_review(row) and not allocation and (not asset or asset.vehicle_type!='trailer'):blockers.append('cost_asset_review_required')
            if projected:blockers.extend(projected['reasons'])
            if inv and db.query(Repair).join(Truck).filter(Truck.tenant_id==tenant,Repair.invoice_number==inv['invoice_number']).first():blockers.append('existing_repair_invoice_review')
            if row:
                if rid in legacy_ro_ids or inv and inv['invoice_id'] in legacy_invoice_ids:
                    blockers.append('existing_repair_source_review')
            action='blocked' if blockers else 'create'
        name=db.query(Truck.name).filter_by(id=repair.truck_id if repair else truck_id,tenant_id=tenant).scalar() if (repair or truck_id) else None
        rows.append({'repair_order_id':rid,'order_number':row['order_number'] if row else link.accepted_payload['order_number'],
            'truck_name':name,'action':action,'repair_id':link.repair_id if link else None,
            'equipment_allocation':allocation,'cost_asset_id':truck_id,'source_revision':row['revision'] if row else None,
            'invoice_id':inv['invoice_id'] if inv else None,'invoice_total':projected['amount'] if projected else None,'source_invoice_total':inv['total_amount'] if inv else None,
            'price_basis':'unresolved' if not projected or projected['reasons'] else 'settlement_principal_plus_applied_card_fees' if row.get('settlement') else 'fee_free_invoice',
            'date_decision':date_decision,'repair_date':when.isoformat() if when else None,'category':category(row) if row else None,'blockers':blockers})
        local.append({'ro':rid,'link':link.id if link else None,'accepted':link.accepted_revision if link else None,
            'state':link.state if link else None,'repair':{'id':repair.id,'asset':repair.truck_id,'date':str(repair.repair_date),'cost':f.money(repair.cost),'category':repair.category,'archived_at':str(repair.archived_at) if repair.archived_at else None} if repair else None})
    local_digest=digest(local)
    body={'version':'db094-financial-plan-v1','source_manifest_digest':value['snapshot_id'],'local_state_digest':local_digest,
          'source_count':value['count'],'selected_count':len(rows),'executable':not any(r['action']=='blocked' for r in rows),
          'rows':rows,'blockers':[f"{r['order_number']}: {b}" for r in rows if r['action']=='blocked' for b in r['blockers']]}
    body['plan_digest']=digest({'tenant_id':tenant,'config':{k:config[k] for k in ('slug','shop_id','bill_to_id','base_url')},'preview':body})
    return body


async def preview_financial(db,tenant,slug,repair_order_ids=None):
    config=d.config(tenant,slug);d.connection(db,tenant,config)
    return build_preview(db,tenant,config,await manifest(config),repair_order_ids)


def operation(db,tenant,slug,kind,key,request):
    if not isinstance(key,str) or not 1<=len(key)<=160:f.fail('Supply an Idempotency-Key.','IDEMPOTENCY_KEY_REQUIRED',422)
    request_digest=digest(request)
    prior=db.query(Operation).filter_by(tenant_id=tenant,slug=slug,kind=kind,key=key).first()
    if prior and prior.request_digest!=request_digest:f.fail('Idempotency key was already used with different content.','IDEMPOTENCY_CONFLICT')
    return prior,request_digest


def save_operation(db,tenant,slug,kind,key,request_digest,result):
    row=Operation(tenant_id=tenant,slug=slug,kind=kind,key=key,request_digest=request_digest,result={})
    db.add(row);db.flush();result={**result,'operation_id':row.id};row.result=result;db.flush()
    return result


def create_repair(db,tenant,config,row,snapshot_id):
    inv=row['invoice'];truck_id,reason,allocation=equipment.resolve(db,tenant,config,row)
    if reason!='cost_treatment_required':f.fail('Unique truck identity is required.','TRUCK_REVIEW_REQUIRED')
    when,date_decision,date_issue=resolved_occurrence(db,tenant,config,row)
    if date_issue or not when:f.fail('Refresh and review service date evidence.','DATE_EVIDENCE_REQUIRED')
    text=work_text(row)
    repair=Repair(truck_id=truck_id,repair_date=when,title=(row['description'] or f"DBN repair {row['order_number']}")[:200],
        details=text or None,description=text or row['order_number'],category=category(row),cost=Decimal(settlement.projection(row)['amount']),
        paid_from_reserve=False,invoice_number=inv['invoice_number'])
    db.add(repair);db.flush()
    content=json.dumps({'shop_id':config['shop_id'],'customer_id':config['bill_to_id'],'source':row,'date_decision':date_decision},sort_keys=True).encode()
    evidence=FinanceEvidence(tenant_id=tenant,sha256=hashlib.sha256(content).hexdigest(),filename=f"dbn-{row['repair_order_id']}.json",
        media_type='application/json',content_base64=base64.b64encode(content).decode(),source_key='dbn-financial:'+digest({'shop':config['shop_id'],'ro':row['repair_order_id']}),
        extraction_version='dieselbridge-financial-v1',extracted={'legacy_repair_ids':[repair.id],'invoice_review':{'source_total':f.money(repair.cost),'quoted_total':inv['total_amount'],'amount_basis':'settlement_principal_plus_applied_card_fees' if row.get('settlement') else 'fee_free_invoice'},'payment_basis':'not_established','date_decision':date_decision,'source':row})
    db.add(evidence);db.flush()
    link=Link(tenant_id=tenant,slug=config['slug'],shop_id=str(config['shop_id']),customer_id=str(config['bill_to_id']),repair_order_id=row['repair_order_id'],repair_id=repair.id,
        accepted_invoice_id=inv['invoice_id'],accepted_revision=inv['revision'],accepted_snapshot_id=snapshot_id,accepted_payload=row,source_settlement_payload=row.get('settlement'),source_payment_review_reasons=[],evidence_id=evidence.id,state='active',review_reason='')
    db.add(link);db.flush()
    if repair.cost>0:
        reference=digest({'tenant':tenant,'shop':config['shop_id'],'ro':row['repair_order_id']})
        bill=f.append_command(db,tenant,Command(effective_date=repair.repair_date,payload={'kind':'bill','legacy_repair_id':repair.id,
            'evidence_id':evidence.id,'source_ref':'dbn-ro:'+reference,'description':repair.title,'amount':f.money(repair.cost),'asset_id':repair.truck_id,'category':'repairs'}),'dbn-bill:'+reference)
        link.bill_event_id=bill.id
        from app.services.accounting_service import create_dieselbridge_bill_journal
        create_dieselbridge_bill_journal(db,repair,source_ref='dbn-ro:'+reference)
    db.flush();return link


async def sync_financial(db,tenant,slug,*,repair_order_ids=None,expected_plan_digest=None,idempotency_key,automatic=False):
    require_enabled();f.lock_business(db,tenant)
    config=d.config(tenant,slug);connection=d.connection(db,tenant,config)
    request={'selection':sorted(repair_order_ids) if repair_order_ids is not None else None,'expected_plan_digest':expected_plan_digest,'automatic':automatic,
             'scope':[str(config['shop_id']),str(config['bill_to_id']),config['base_url']]}
    prior,request_digest=operation(db,tenant,slug,'sync',idempotency_key,request)
    if prior:return prior.result
    value=await manifest(config);preview=build_preview(db,tenant,config,value,repair_order_ids)
    if not automatic and expected_plan_digest!=preview['plan_digest']:f.fail('Financial records or source changed. Refresh the preview.','STALE_PLAN')
    if not automatic and not preview['executable']:f.fail('Resolve every selected repair before importing this batch.','BATCH_BLOCKED')
    items={r['repair_order_id']:r for r in value['items']}
    result={'created':0,'unchanged':0,'review_required':0,'blocked':0,'plan_digest':preview['plan_digest']}
    for planned in preview['rows']:
        action=planned['action'];row=items.get(planned['repair_order_id'])
        existing=db.query(Link).filter_by(tenant_id=tenant,shop_id=str(config['shop_id']),repair_order_id=planned['repair_order_id']).first()
        if existing and row and row['authorization']=='authorized':
            preserve_settlement_observation(db,tenant,existing,row)
            existing.source_settlement_payload=row.get('settlement')
            existing.source_payment_review_reasons=source_claim_issues(db,tenant,existing,row)+settlement.projection(row)['reasons']
        if action=='create':create_repair(db,tenant,config,row,value['snapshot_id']);result['created']+=1
        elif action=='review_required':
            link=db.query(Link).filter_by(tenant_id=tenant,shop_id=str(config['shop_id']),repair_order_id=planned['repair_order_id']).one()
            link.state='access_removed' if not row or row['authorization']!='authorized' else 'review_required'
            link.review_reason=planned['blockers'][0];link.latest_payload=row if row and row['authorization']=='authorized' else None
            result['review_required']+=1
        else:result['blocked' if action=='blocked' else 'unchanged']+=1
    if result['created']:db.add(connection)
    return save_operation(db,tenant,slug,'sync',idempotency_key,request_digest,result)


def require_active_revision(link,revision):
    if link.state!='active':f.fail('Review the changed or unavailable source invoice before recording payment.','REVIEW_REQUIRED')
    if link.accepted_revision!=revision:f.fail('Repair invoice changed. Refresh before recording payment.','STALE_INVOICE')


def preserved_payment_receipt(db,tenant,evidence_id):
    proof=f.evidence(db,tenant,evidence_id)
    # Only original uploaded bytes can support an owner attestation. An internal
    # invoice, generated confirmation or another payment attestation is not a
    # second physical receipt, even when it concerns a different repair.
    if proof.extraction_version!='elis-evidence-v1' or db.query(FinanceEvidence).filter_by(tenant_id=tenant,supersedes_id=proof.id).first():
        f.fail('Select an original, current uploaded payment receipt, not an invoice import or generated confirmation.','PAYMENT_EVIDENCE_REQUIRED')
    try:
        content=base64.b64decode(proof.content_base64,validate=True)
        actual_sha=hashlib.sha256(content).hexdigest()
        if not content or actual_sha!=proof.sha256:raise ValueError()
    except (ValueError,TypeError):
        f.fail('Preserved payment receipt bytes do not match their recorded hash.','PAYMENT_EVIDENCE_INTEGRITY')
    return proof,actual_sha


def require_receipt_unallocated(db,tenant,receipt_sha):
    # Until grouped receipt allocation is explicitly designed, one physical
    # receipt can support one active owner payment across the entire business.
    # Tenant serialization in the enclosing Finance command prevents races.
    for recorded in db.query(Payment).filter_by(tenant_id=tenant,payer='owner',reversal_event_id=None).all():
        proof=f.evidence(db,tenant,recorded.evidence_id)
        if proof.extracted.get('preserved_evidence_sha256')==receipt_sha:
            f.fail('This payment receipt already supports an active recorded payment. Reverse an incorrect allocation before reusing it.','DUPLICATE_PAYMENT')


def record_verified_payment(db,tenant,repair_id,body,key):
    require_enabled();f.lock_business(db,tenant);link=scoped_link(db,tenant,repair_id)
    request={'repair_id':repair_id,'body':body.model_dump(mode='json')}
    prior,request_digest=operation(db,tenant,link.slug,'payment',key,request)
    if prior:return prior.result
    require_active_revision(link,body.expected_revision)
    if not link.bill_event_id:f.fail('This invoice has no amount payable.','NO_PAYABLE')
    if body.paid_date>date.today():f.fail('Payment date cannot be in the future.','INVALID_PAYMENT_DATE',422)
    evidence_id=body.evidence_id
    source_claim=source_claim_request(body)
    if source_claim:validate_source_claim(db,tenant,link,source_claim,body.amount,body.paid_date,body.payer)
    if body.payer=='owner':
        if not body.owner_payment_confirmed or not evidence_id:f.fail('Confirm the actual personal payment and select its preserved receipt.','PAYMENT_EVIDENCE_REQUIRED')
        proof,receipt_sha=preserved_payment_receipt(db,tenant,evidence_id)
        require_receipt_unallocated(db,tenant,receipt_sha)
        attestation={'kind':'verified_owner_repair_payment','claim_id':link.bill_event_id,'amount':f.money(body.amount),
            'paid_date':body.paid_date.isoformat(),'preserved_evidence_id':proof.id,'preserved_evidence_sha256':receipt_sha,'note':body.note}
        if source_claim:attestation['source_payment_claim']=source_claim
        raw=json.dumps(attestation,sort_keys=True).encode();sha=hashlib.sha256(raw).hexdigest()
        existing=db.query(FinanceEvidence).filter_by(tenant_id=tenant,sha256=sha).first()
        if existing and db.query(Payment).filter_by(tenant_id=tenant,evidence_id=existing.id,reversal_event_id=None).first():
            f.fail('This exact owner payment was already recorded. Review its existing entry.','DUPLICATE_PAYMENT')
        if not existing:
            existing=FinanceEvidence(tenant_id=tenant,sha256=sha,filename='verified-owner-repair-payment.json',media_type='application/json',
                content_base64=base64.b64encode(raw).decode(),source_key=f'dbn-owner-payment:{link.id}',extraction_version='db094-owner-payment-v1',extracted=attestation)
            db.add(existing);db.flush()
        evidence_id=existing.id
    elif body.owner_payment_confirmed:
        f.fail('Owner payment attestation applies only to personal payments.','INVALID_PAYMENT_EVIDENCE',422)
    if source_claim and body.payer!='owner':
        facts={'source_payment_claim':source_claim,'claim_id':link.bill_event_id,'amount':f.money(body.amount),'paid_date':body.paid_date.isoformat(),'note':body.note}
        raw=json.dumps(facts,sort_keys=True).encode();sha=hashlib.sha256(raw).hexdigest()
        proof=db.query(FinanceEvidence).filter_by(tenant_id=tenant,sha256=sha).first()
        if not proof:
            proof=FinanceEvidence(tenant_id=tenant,sha256=sha,filename='verified-source-payment.json',media_type='application/json',content_base64=base64.b64encode(raw).decode(),source_key='dbn-payment-claim:'+str(link.id),extraction_version='db094-source-payment-verification-v2',extracted=facts)
            db.add(proof);db.flush()
        evidence_id=proof.id
    event=f.append_command(db,tenant,Command(effective_date=body.paid_date,payload={'kind':'payment','claim_id':link.bill_event_id,
        'amount':f.money(body.amount),'payer':body.payer,'transaction_id':body.transaction_id,'evidence_id':evidence_id}),
        'dbn-payment:'+digest({'tenant':tenant,'slug':link.slug,'key':key}))
    project_verified_repair_payment(db,tenant,event)
    return save_operation(db,tenant,link.slug,'payment',key,request_digest,public_state(db,tenant,link))


def project_verified_repair_payment(db,tenant,event):
    if event.kind!='payment':return None
    link=db.query(Link).filter_by(tenant_id=tenant,bill_event_id=event.payload['claim_id']).first()
    if not link:return None  # Reimbursement/card repayment is not a second repair payment.
    require_enabled();require_active_revision(link,link.accepted_revision)
    if event.effective_date>date.today():
        f.fail('Payment date cannot be in the future.','INVALID_PAYMENT_DATE',422)
    prior=db.query(Payment).filter_by(tenant_id=tenant,event_id=event.id).first()
    if prior:return prior
    p=event.payload
    if p['payer']=='owner':
        proof=f.evidence(db,tenant,p.get('evidence_id'))
        facts=proof.extracted
        if (proof.extraction_version!='db094-owner-payment-v1' or facts.get('claim_id')!=link.bill_event_id
                or facts.get('amount')!=f.money(p['amount']) or facts.get('paid_date')!=event.effective_date.isoformat()):
            f.fail('Explicit verified owner payment facts are required.','PAYMENT_EVIDENCE_REQUIRED')
        original,receipt_sha=preserved_payment_receipt(db,tenant,facts.get('preserved_evidence_id'))
        if receipt_sha!=facts.get('preserved_evidence_sha256'):
            f.fail('Owner payment evidence changed or was already used.','PAYMENT_EVIDENCE_REQUIRED')
        require_receipt_unallocated(db,tenant,receipt_sha)
    claim=None
    if p.get('evidence_id'):
        proof=f.evidence(db,tenant,p['evidence_id'])
        claim=proof.extracted.get('source_payment_claim')
        if claim:
            if proof.extracted.get('claim_id')!=link.bill_event_id or proof.extracted.get('amount')!=f.money(p['amount']) or proof.extracted.get('paid_date')!=event.effective_date.isoformat():
                f.fail('Source payment verification evidence does not match this payment.','PAYMENT_EVIDENCE_REQUIRED')
            validate_source_claim(db,tenant,link,claim,p['amount'],event.effective_date,p['payer'])
    repair=db.query(Repair).filter_by(id=link.repair_id).one()
    payment=Payment(tenant_id=tenant,link_id=link.id,event_id=event.id,amount=f.D(p['amount']),paid_date=event.effective_date,payer=p['payer'],evidence_id=p.get('evidence_id'),source_attempt_id=claim['attempt_id'] if claim else None,source_attempt_revision=claim['revision'] if claim else None,source_shop_id=link.shop_id if claim else None)
    db.add(payment);db.flush()
    if event.effective_date>=RESERVE_REGIME_START_DATE:
        reserve=RepairReserveLedger(tenant_id=tenant,truck_id=repair.truck_id,entry_date=event.effective_date,entry_type='withdrawal',
            amount=payment.amount,description=f'Verified DBN payment: {repair.invoice_number}',source_type='dbn_payment',source_id=payment.id)
        db.add(reserve);db.flush();payment.reserve_withdrawal_id=reserve.id
    from app.services.accounting_service import create_dieselbridge_payment_journal
    create_dieselbridge_payment_journal(db,repair,payment_id=payment.id,amount=payment.amount,paid_date=payment.paid_date,payer=payment.payer)
    db.flush();return payment


def require_managed_claim_review(db,tenant,payload):
    claim_id=payload.get('claim_id')
    if payload.get('kind')=='reversal' and payload.get('posting_id'):
        posting=db.query(FinancePosting).filter_by(id=payload['posting_id'],tenant_id=tenant).first()
        claim_id=posting.event_id if posting else None
    if claim_id and db.query(Link).filter_by(tenant_id=tenant,bill_event_id=claim_id).first():
        f.fail('Source-linked invoice credits and reversals require an explicit invoice correction review.','DBN_INVOICE_REVIEW_REQUIRED')


def reverse_verified_payment(db,tenant,repair_id,payment_id,body,key):
    require_enabled();f.lock_business(db,tenant);link=scoped_link(db,tenant,repair_id)
    prior,request_digest=operation(db,tenant,link.slug,'payment_reversal',key,{'repair_id':repair_id,'payment_id':payment_id,'body':body.model_dump(mode='json')})
    if prior:return prior.result
    if body.expected_revision!=link.accepted_revision:f.fail('Repair invoice changed. Refresh before correction.','STALE_INVOICE')
    payment=db.query(Payment).filter_by(id=payment_id,tenant_id=tenant,link_id=link.id).first()
    if not payment:f.fail('Payment not found.','RESOURCE_NOT_FOUND',404)
    if payment.reversal_event_id:f.fail('Payment already reversed.','PAYMENT_ALREADY_REVERSED')
    if body.reversal_date>date.today():f.fail('Reversal date cannot be in the future.','INVALID_PAYMENT_DATE',422)
    posting=db.query(FinancePosting).filter_by(tenant_id=tenant,event_id=payment.event_id).one()
    event=f.append_command(db,tenant,Command(effective_date=body.reversal_date,payload={'kind':'reversal','posting_id':posting.id,'reason':body.reason}),
        'dbn-payment-reversal:'+digest({'tenant':tenant,'slug':link.slug,'key':key}))
    project_verified_repair_payment_reversal(db,tenant,event)
    return save_operation(db,tenant,link.slug,'payment_reversal',key,request_digest,public_state(db,tenant,link))


def project_verified_repair_payment_reversal(db,tenant,event):
    if event.kind!='reversal':return None
    original=db.query(FinancePosting).filter_by(tenant_id=tenant,id=event.payload['posting_id']).first()
    if not original:return None
    payment=db.query(Payment).filter_by(tenant_id=tenant,event_id=original.event_id).first()
    if not payment:return None
    require_enabled()
    if event.effective_date>date.today():
        f.fail('Reversal date cannot be in the future.','INVALID_PAYMENT_DATE',422)
    if payment.reversal_event_id:
        if payment.reversal_event_id==event.id:return payment
        f.fail('Payment already reversed.','PAYMENT_ALREADY_REVERSED')
    if payment.reserve_withdrawal_id:
        withdrawal=db.query(RepairReserveLedger).filter_by(id=payment.reserve_withdrawal_id,tenant_id=tenant).one()
        reverse=RepairReserveLedger(tenant_id=tenant,truck_id=withdrawal.truck_id,entry_date=event.effective_date,
            entry_type='withdrawal_reversal',amount=payment.amount,description='Verified DBN payment reversal',
            source_type='dbn_payment_reverse',source_id=payment.id,reversal_of_id=withdrawal.id)
        db.add(reverse);db.flush();payment.reversal_reserve_id=reverse.id
    payment.reversal_event_id=event.id
    from app.services.accounting_service import reverse_dieselbridge_payment_journal
    reverse_dieselbridge_payment_journal(db,payment_id=payment.id,reversal_date=event.effective_date,reason=event.payload['reason'],tenant_id=tenant)
    db.flush();return payment


async def authorized_cancellation(config,invoice_id):
    """A missing current manifest row is not proof of cancellation.

    Refetch the existing authorized invoice export, including cancelled versions.
    Revocation/removal or a still-finalized invoice cannot erase an EDG expense.
    """
    client=d.SourceClient(config)
    upper=datetime.now(timezone.utc).isoformat()
    params={'updated_since':d.EPOCH,'updated_before':upper,'limit':100}
    seen=set();found=None
    for _ in range(100):
        page=await client.page(params)
        if not isinstance(page,dict) or not isinstance(page.get('items'),list) or len(page['items'])>100 or d.timestamp(page.get('watermark'))!=d.timestamp(upper):protocol()
        for item in page['items']:
            kind=d.validate_item(item,config)
            if kind=='invoice' and item['invoice_id']==invoice_id:
                if found is not None and found!=item:protocol()
                found=item
        cursor=page.get('next_cursor')
        if not cursor:break
        if not isinstance(cursor,str) or cursor in seen:protocol()
        seen.add(cursor);params['cursor']=cursor
    else:protocol()
    if found and (found['status']=='cancelled' or found.get('voided_at')):
        return found
    return None


def capture_invoice_evidence(db,tenant,config,row,*,note,repair_id=None,supersedes_id=None):
    _,date_decision,_=resolved_occurrence(db,tenant,config,row) if row.get('invoice') else (None,None,None)
    raw=json.dumps({'date_decision':date_decision,'shop_id':config['shop_id'],'customer_id':config['bill_to_id'],'source':row,'review_note':note,
        'repair_id':repair_id,'supersedes_id':supersedes_id},sort_keys=True).encode()
    sha=hashlib.sha256(raw).hexdigest()
    prior=db.query(FinanceEvidence).filter_by(tenant_id=tenant,sha256=sha).first()
    if prior:return prior
    previous=f.evidence(db,tenant,supersedes_id) if supersedes_id else None
    extracted={'source':row,'date_decision':date_decision,'review_note':note,'payment_basis':'not_established'}
    if repair_id:extracted['legacy_repair_ids']=[repair_id]
    if row.get('invoice'):extracted['invoice_review']={'source_total':settlement.projection(row)['amount'],'quoted_total':row['invoice']['total_amount'],'amount_basis':'settlement_principal_plus_applied_card_fees' if row.get('settlement') else 'fee_free_invoice'}
    evidence=FinanceEvidence(tenant_id=tenant,sha256=sha,filename=f"dbn-source-review-{row['repair_order_id']}.json",media_type='application/json',
        content_base64=base64.b64encode(raw).decode(),source_key=previous.source_key if previous else 'dbn-review:'+digest({'shop':config['shop_id'],'ro':row['repair_order_id']}),
        supersedes_id=supersedes_id,extraction_version='dieselbridge-financial-v1',extracted=extracted)
    db.add(evidence);db.flush();return evidence


async def review_preview(db,tenant,repair_id,expected_revision):
    link=scoped_link(db,tenant,repair_id)
    if link.accepted_revision!=expected_revision:f.fail('Accepted invoice changed. Refresh before review.','STALE_INVOICE')
    config=d.config(tenant,link.slug);d.connection(db,tenant,config)
    if (link.shop_id,link.customer_id)!=(str(config['shop_id']),str(config['bill_to_id'])):f.fail('Connection scope changed.','CONNECTION_SCOPE_CHANGED')
    value=await manifest(config)
    row=next((r for r in value['items'] if r['repair_order_id']==link.repair_order_id),None)
    repair=db.query(Repair).filter_by(id=repair_id).execution_options(include_archived_repairs=True).one()
    if repair.archived_at:f.fail('Restoring an archived source repair requires an explicit archive restoration review.','REPAIR_RESTORE_REVIEW_REQUIRED')
    state=public_state(db,tenant,link)
    payments=db.query(Payment).filter_by(tenant_id=tenant,link_id=link.id).order_by(Payment.id).all()
    active_payments=[p for p in payments if not p.reversal_event_id]
    blockers=[];after=None;proof=None;action='blocked'
    before={'invoice_id':link.accepted_invoice_id,'invoice_number':link.accepted_payload['invoice']['invoice_number'],
            'cost':f.money(repair.cost),'repair_date':repair.repair_date.isoformat(),'description':repair.details or repair.description or repair.title,
            'category':repair.category}
    if row and row['authorization']=='authorized':
        inv=row['invoice'];when,date_decision,date_issue=resolved_occurrence(db,tenant,config,row);truck_id,reason,allocation=equipment.resolve(db,tenant,config,row)
        if date_issue:blockers.append(date_issue)
        if reason!='cost_treatment_required' or truck_id!=repair.truck_id:blockers.append('TRUCK_IDENTITY_REVIEW_REQUIRED')
        asset=db.query(Truck).filter_by(id=truck_id,tenant_id=tenant).first() if truck_id else None
        if needs_asset_review(row) and not allocation and (not asset or asset.vehicle_type!='trailer'):blockers.append('COST_ASSET_REVIEW_REQUIRED')
        if not when:blockers.append('DATE_EVIDENCE_REQUIRED')
        blockers.extend(settlement.projection(row)['reasons'])
        blockers.extend(source_claim_issues(db,tenant,link,row))
        after={'invoice_id':inv['invoice_id'],'invoice_number':inv['invoice_number'],'cost':settlement.projection(row)['amount'],
               'date_decision':date_decision,'repair_date':when.isoformat() if when else None,'description':work_text(row),'category':category(row)}
        action='no_change' if when==repair.repair_date and inv['invoice_id']==link.accepted_invoice_id and inv['revision']==link.accepted_revision and row['revision']==link.accepted_payload['revision'] and settlement.projection(row)['amount'] is not None and Decimal(settlement.projection(row)['amount'])==Decimal(repair.cost) else 'replace_unpaid_invoice'
    else:
        proof=await authorized_cancellation(config,link.accepted_invoice_id)
        if proof:
            action='cancel_unpaid_invoice'
            after={**before,'cost':'0.00'}
        else:blockers.append('AUTHORIZED_CANCELLATION_OR_CURRENT_INVOICE_REQUIRED')
    if active_payments and action!='no_change':blockers.append('PAYMENT_CORRECTION_REQUIRED')
    if action in ('replace_unpaid_invoice','cancel_unpaid_invoice'):
        closed={}
        for e in f.events(db,tenant):
            if e.kind in ('close_period','reopen_period'):closed[(e.payload['start'],e.payload['end'])]=e.kind=='close_period'
        old_bill=db.query(FinanceEvent).filter_by(tenant_id=tenant,id=link.bill_event_id).first() if link.bill_event_id else None
        dates=[repair.repair_date,old_bill.effective_date if old_bill else None,
               date.fromisoformat(after['repair_date']) if after and after.get('repair_date') else None]
        if any(active and any(day and start<=day.isoformat()<=end for day in dates) for (start,end),active in closed.items()):
            blockers.append('PERIOD_CLOSED')
    local={'repair':before,'link_id':link.id,'accepted_revision':link.accepted_revision,'bill_event_id':link.bill_event_id,
           'payments':[{'id':p.id,'event_id':p.event_id,'amount':f.money(p.amount),'reversal_event_id':p.reversal_event_id} for p in payments]}
    result={'repair_id':repair_id,'accepted_revision':link.accepted_revision,'action':action,'can_apply':not blockers and (action in ('replace_unpaid_invoice','cancel_unpaid_invoice') or action=='no_change' and link.state!='active'),
            'before':before,'after':after,'recorded_paid_amount':state['recorded_paid_amount'],'blockers':blockers,
            'candidate_pdf_url':f'/api/v1/accounting/dieselbridge/repairs/{repair_id}/source-review/pdf' if row and row['authorization']=='authorized' else None}
    result['review_digest']=digest({'tenant':tenant,'scope':[link.slug,link.shop_id,link.customer_id],
        'manifest':value['snapshot_id'],'candidate':row,'cancellation_proof':proof,'local':local,'review':result})
    return result,value,row,proof


async def apply_source_review(db,tenant,repair_id,body,key):
    require_enabled();f.lock_business(db,tenant);link=scoped_link(db,tenant,repair_id)
    request={'repair_id':repair_id,'body':body.model_dump(mode='json')}
    prior,request_digest=operation(db,tenant,link.slug,'source_review',key,request)
    if prior:return prior.result
    preview,value,row,proof=await review_preview(db,tenant,repair_id,body.expected_revision)
    if preview['review_digest']!=body.expected_review_digest:f.fail('Source, payment or repair facts changed. Refresh the review.','STALE_SOURCE_REVIEW')
    if not preview['can_apply']:f.fail('Resolve the source review blockers before changing booked costs.','SOURCE_REVIEW_BLOCKED')
    config=d.config(tenant,link.slug);repair=db.query(Repair).filter_by(id=repair_id).one()
    link.state='review_required'
    from app.services.accounting_service import replace_dieselbridge_bill
    if preview['action']=='replace_unpaid_invoice':
        inv=row['invoice'];when,_,_=resolved_occurrence(db,tenant,config,row)
        evidence=capture_invoice_evidence(db,tenant,config,row,note=body.note,repair_id=repair.id,supersedes_id=link.evidence_id)
        repair.cost=Decimal(settlement.projection(row)['amount']);repair.repair_date=when
        text=work_text(row);repair.title=(row['description'] or f"DBN repair {row['order_number']}")[:200]
        repair.details=text or None;repair.description=text or row['order_number'];repair.category=category(row);repair.invoice_number=inv['invoice_number']
        event=replace_dieselbridge_bill(db,tenant,link,amount=repair.cost,effective_date=when,evidence_id=evidence.id,
            description=repair.title,source_ref='dbn-reviewed:'+digest({'link':link.id,'revision':row['revision']}),operation_key='dbn-review:'+digest({'tenant':tenant,'key':key}))
        link.bill_event_id=event.id if event else link.bill_event_id
        link.accepted_invoice_id=inv['invoice_id'];link.accepted_revision=inv['revision'];link.accepted_payload=row
        link.accepted_snapshot_id=value['snapshot_id'];link.evidence_id=evidence.id;link.state='active';link.review_reason='';link.latest_payload=None
        link.source_settlement_payload=row.get('settlement');link.source_payment_review_reasons=[]
    elif preview['action']=='cancel_unpaid_invoice':
        # Authorized cancelled invoice proof is retained; absence alone never
        # archives a booked repair. Original amount/date remain in the archive.
        evidence=capture_invoice_evidence(db,tenant,config,{'repair_order_id':link.repair_order_id,'revision':digest(proof),'cancelled_invoice':proof},note=body.note)
        replace_dieselbridge_bill(db,tenant,link,amount=f.ZERO,effective_date=repair.repair_date,evidence_id=evidence.id,
            description='Approved DBN invoice cancellation',source_ref='dbn-cancel:'+digest(proof),operation_key='dbn-review:'+digest({'tenant':tenant,'key':key}))
        repair.archived_at=datetime.now(timezone.utc);repair.archive_reason='Approved source invoice cancellation: '+body.note[:400]
        repair.archive_operation_id='dbn-review:'+digest({'tenant':tenant,'key':key})
        link.state='cancelled';link.review_reason='approved_source_cancellation';link.latest_payload={'cancellation':proof,'evidence_id':evidence.id}
    else:
        link.state='active';link.review_reason='';link.latest_payload=None
    db.flush()
    return save_operation(db,tenant,link.slug,'source_review',key,request_digest,{'action':preview['action'],'repair_id':repair_id,'review_digest':preview['review_digest']})
