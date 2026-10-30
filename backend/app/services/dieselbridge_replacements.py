"""Reviewed temporary-record archive/restore. Flush only; caller owns transaction.

This corrects existing bookkeeping, never establishes a payment. Original rows,
receipts, journals and withdrawals survive. Finance claims require separate
review rather than guessing how to reverse their dependent payments.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import inspect
from app.models.repair import Repair
from app.models.truck import Truck
from app.models.dieselbridge import DieselBridgeRepairLink as Link, DieselBridgeInvoice, DieselBridgeFinancialOperation as Operation
from app.models.finance import FinanceEvent
from app.models.repair_reserve_ledger import RepairReserveLedger as Reserve
from app.models.journal_entry import JournalEntry as Journal
from app.models.journal_entry_line import JournalEntryLine as Line
from app.models.chart_of_accounts import ChartOfAccount as Account
from app.services import dieselbridge as d, dieselbridge_financial as financial, finance as f


def facts(obj):
    def stable(value):
        if isinstance(value,datetime):
            if value.tzinfo:value=value.astimezone(timezone.utc).replace(tzinfo=None)
            return value.isoformat(timespec='microseconds')
        return str(value) if value is not None else None
    return {c.key:stable(getattr(obj,c.key)) for c in inspect(type(obj)).columns}


def require_open(db,tenant,dates):
    closed={}
    for e in f.events(db,tenant):
        if e.kind in ('close_period','reopen_period'):
            closed[(e.payload['start'],e.payload['end'])]=e.kind=='close_period'
    if any(active and start<=str(day)<=end for (start,end),active in closed.items() for day in dates if day):
        f.fail('Replacement affects a closed period. Reopen it through Finance review first.','PERIOD_CLOSED')


def validate_date(day):
    if day>date.today():f.fail('Correction date cannot be in the future.','INVALID_CORRECTION_DATE',422)


def scoped_repair(db,tenant,rid):
    row=db.query(Repair).join(Truck,Truck.id==Repair.truck_id).filter(Repair.id==rid,Truck.tenant_id==tenant).execution_options(include_archived_repairs=True).first()
    if not row:f.fail('Repair not found.','RESOURCE_NOT_FOUND',404)
    return row


def candidates(db,tenant,repair_id):
    financial.scoped_link(db,tenant,repair_id)
    new=scoped_repair(db,tenant,repair_id)
    managed={x.repair_id for x in db.query(Link).filter_by(tenant_id=tenant)}
    managed|={x.repair_id for x in db.query(DieselBridgeInvoice).filter_by(tenant_id=tenant) if x.repair_id}
    return {'items':[{'id':x.id,'title':x.title or x.description or 'Untitled repair','date':str(x.repair_date) if x.repair_date else None,'cost':f.money(x.cost) if x.cost is not None else None}
        for x in db.query(Repair).filter_by(truck_id=new.truck_id).order_by(Repair.repair_date,Repair.id) if x.id not in managed and not x.archive_operation_id]}


def audit_summaries(db,tenant,link):
    operations=db.query(Operation).filter_by(tenant_id=tenant,slug=link.slug,kind='temp_replace').filter(Operation.result['plan']['repair_order_id'].as_string()==link.repair_order_id).order_by(Operation.id).all()
    restored={x.result['replacement_operation_id'] for x in db.query(Operation).filter_by(tenant_id=tenant,slug=link.slug,kind='temp_restore')}
    return [{'id':x.id,'reason':x.result['reason'],'restored':x.id in restored,'repair_ids':[r['repair_id'] for r in x.result['corrections']]} for x in operations]


async def target(db,tenant,slug,rid):
    config=d.config(tenant,slug)
    link=db.query(Link).filter_by(tenant_id=tenant,slug=slug,shop_id=str(config['shop_id']),customer_id=str(config['bill_to_id']),repair_order_id=rid).first()
    if not link:f.fail('Import and reconcile the authorized source repair before replacing temporary records.','ACCEPTED_TARGET_REQUIRED')
    repair=scoped_repair(db,tenant,link.repair_id)
    value=await financial.manifest(config)
    review=financial.build_preview(db,tenant,config,value,[rid])
    if link.state!='active' or repair.archived_at or review['rows'][0]['action']!='unchanged':
        f.fail('Source target changed or is unavailable. Review it first.','TARGET_REVIEW_REQUIRED')
    return link,repair,review['plan_digest']


def legacy_facts(db,tenant,repair,target_id):
    if repair.id==target_id or repair.archived_at or repair.archive_operation_id:
        f.fail('Choose an active temporary repair that has not already been replaced.','REPLACEMENT_REVIEW_REQUIRED')
    if db.query(Link).filter_by(tenant_id=tenant,repair_id=repair.id).first() or db.query(DieselBridgeInvoice).filter_by(tenant_id=tenant,repair_id=repair.id).first():
        f.fail('Managed invoice repairs require their own source review.','MANAGED_REPAIR')
    claims=[e for e in f.events(db,tenant) if e.payload.get('legacy_repair_id')==repair.id]
    if claims:f.fail('Temporary repair has Finance claims. Review their dependent effects separately.','FINANCE_CLAIM_REVIEW_REQUIRED')
    withdrawals=db.query(Reserve).filter_by(source_type='repair',source_id=repair.id).order_by(Reserve.id).all()
    for w in withdrawals:
        if w.tenant_id!=tenant or w.truck_id!=repair.truck_id or w.entry_type!='withdrawal' or w.amount<=0 or db.query(Reserve).filter_by(reversal_of_id=w.id).first():
            f.fail('Reserve effects are inconsistent or already corrected.','RESERVE_REVIEW_REQUIRED')
    journals=db.query(Journal).filter_by(reference_type='repair',reference_id=repair.id).order_by(Journal.id).all()
    journal_facts=[]
    for j in journals:
        lines=db.query(Line).filter_by(journal_entry_id=j.id).order_by(Line.id).all()
        if j.tenant_id!=tenant or j.truck_id not in (None,repair.truck_id) or not lines:
            f.fail('Journal scope requires review.','JOURNAL_REVIEW_REQUIRED')
        for line in lines:
            account=db.get(Account,line.account_id)
            if line.tenant_id!=tenant or line.truck_id not in (None,repair.truck_id) or not account or account.tenant_id!=tenant or account.truck_id not in (None,repair.truck_id) or line.debit<0 or line.credit<0:
                f.fail('Journal lines require review.','JOURNAL_REVIEW_REQUIRED')
        if sum(x.debit for x in lines)!=sum(x.credit for x in lines):f.fail('Journal is unbalanced.','JOURNAL_REVIEW_REQUIRED')
        if db.query(Journal).filter_by(tenant_id=tenant,reference_type='dbn_temp_reverse',reference_id=j.id).first():
            f.fail('Journal was already corrected.','JOURNAL_REVIEW_REQUIRED')
        journal_facts.append({'entry':facts(j),'lines':[facts(x) for x in lines]})
    return {'repair':facts(repair),'withdrawals':[facts(w) for w in withdrawals],'journals':journal_facts}


async def preview(db,tenant,slug,body):
    validate_date(body.correction_date)
    ids=body.legacy_repair_ids
    if len(ids)!=len(set(ids)) or any(type(x)!=int or x<=0 for x in ids):f.fail('Select each temporary repair once.','INVALID_SELECTION',422)
    link,new,source_digest=await target(db,tenant,slug,body.repair_order_id)
    rows=[]
    for rid in sorted(ids):
        old=scoped_repair(db,tenant,rid)
        if old.truck_id!=new.truck_id:f.fail('Temporary and source repairs must identify the same equipment.','ASSET_REVIEW_REQUIRED')
        rows.append(legacy_facts(db,tenant,old,new.id))
    original_dates=[r['repair']['repair_date'] for r in rows]+[w['entry_date'] for r in rows for w in r['withdrawals']]+[j['entry']['entry_date'] for r in rows for j in r['journals']]
    if any(day and day>str(body.correction_date) for day in original_dates):f.fail('Correction cannot precede an original repair or bookkeeping effect.','INVALID_CORRECTION_DATE',422)
    if any(not r['repair']['repair_date'] and (r['withdrawals'] or r['journals']) for r in rows):f.fail('An undated repair with bookkeeping effects needs date reconciliation first.','DATE_EVIDENCE_REQUIRED')
    require_open(db,tenant,[body.correction_date]+original_dates)
    result={'version':'db094-temporary-replacement-v1','tenant_id':tenant,'slug':slug,'repair_order_id':body.repair_order_id,'target_repair':facts(new),'source_plan_digest':source_digest,'correction_date':str(body.correction_date),'temporary_records':rows,
            'expense_removed':f.money(sum((Decimal(r['repair']['cost'] or '0') for r in rows),f.ZERO)),
            'reserve_correction':f.money(sum((Decimal(w['amount']) for r in rows for w in r['withdrawals']),f.ZERO)),
            'payment_created':False,'notice':'Existing ledger corrections only; no payment, refund or funding is inferred. Restoring returns the pre-replacement state; the source repair remains active.'}
    result['plan_digest']=financial.digest(result)
    return result


def reverse_journal(db,tenant,original,day,reference_type,reason):
    j=Journal(tenant_id=tenant,truck_id=original.truck_id,entry_date=day,reference_type=reference_type,reference_id=original.id,description=reason)
    db.add(j);db.flush()
    for line in db.query(Line).filter_by(journal_entry_id=original.id).all():
        db.add(Line(tenant_id=tenant,journal_entry_id=j.id,account_id=line.account_id,truck_id=line.truck_id,debit=line.credit,credit=line.debit,description=reason))
    db.flush();return j.id


async def apply(db,tenant,slug,body,key,author='internal-review'):
    financial.require_enabled();f.lock_business(db,tenant)
    prior,request_digest=financial.operation(db,tenant,slug,'temp_replace',key,{'body':body.model_dump(mode='json'),'author':author})
    if prior:return prior.result
    if not body.confirmed_same_job or not body.reviewed_existing_effects:f.fail('Confirm the job identity and each existing bookkeeping effect.','REPLACEMENT_CONFIRMATION_REQUIRED')
    plan=await preview(db,tenant,slug,body)
    if plan['plan_digest']!=body.expected_plan_digest:f.fail('Replacement facts changed. Refresh the preview.','STALE_PLAN')
    marker='dbn-temp:'+financial.digest({'tenant':tenant,'slug':slug,'key':key})
    corrections=[]
    for row in plan['temporary_records']:
        old=scoped_repair(db,tenant,int(row['repair']['id']))
        old.archived_at=datetime.now(timezone.utc);old.replaced_by_repair_id=int(plan['target_repair']['id']);old.archive_operation_id=marker;old.archive_reason=body.reason
        reserves=[];journals=[]
        for w in row['withdrawals']:
            reversal=Reserve(tenant_id=tenant,truck_id=old.truck_id,entry_date=body.correction_date,entry_type='withdrawal_reversal',amount=Decimal(w['amount']),source_type='dbn_temp_reverse',source_id=int(w['id']),reversal_of_id=int(w['id']),description='Reviewed temporary repair replacement')
            db.add(reversal);db.flush();reserves.append(facts(reversal))
        for j in row['journals']:
            jid=reverse_journal(db,tenant,db.get(Journal,int(j['entry']['id'])),body.correction_date,'dbn_temp_reverse',body.reason)
            journals.append(jid)
        db.flush();corrections.append({'repair_id':old.id,'archived_snapshot':facts(old),'reserve_reversals':reserves,'journal_reversals':journals,
            'journal_snapshots':[{'entry':facts(db.get(Journal,jid)),'lines':[facts(x) for x in db.query(Line).filter_by(journal_entry_id=jid).order_by(Line.id)]} for jid in journals]})
    return financial.save_operation(db,tenant,slug,'temp_replace',key,request_digest,{'plan':plan,'archive_marker':marker,'corrections':corrections,'reason':body.reason,'author':author,'confirmed_same_job':True,'reviewed_existing_effects':True,'reviewed_at':datetime.now(timezone.utc).isoformat()})


async def restore_preview(db,tenant,slug,operation_id,body):
    validate_date(body.correction_date)
    op=db.query(Operation).filter_by(id=operation_id,tenant_id=tenant,slug=slug,kind='temp_replace').first()
    if not op:f.fail('Replacement operation not found.','RESOURCE_NOT_FOUND',404)
    if str(body.correction_date)<op.result['plan']['correction_date']:f.fail('Restoration cannot precede the replacement.','INVALID_CORRECTION_DATE',422)
    if db.query(Operation).filter_by(tenant_id=tenant,slug=slug,kind='temp_restore').filter(Operation.result['replacement_operation_id'].as_integer()==operation_id).first():
        f.fail('Replacement was already restored.','ALREADY_RESTORED')
    link,new,source_digest=await target(db,tenant,slug,op.result['plan']['repair_order_id'])
    if facts(new)!=op.result['plan']['target_repair']:f.fail('Source target changed. Review restoration separately.','STALE_TARGET')
    dates=[body.correction_date]
    for row in op.result['corrections']:
        old=scoped_repair(db,tenant,row['repair_id'])
        if facts(old)!=row['archived_snapshot']:f.fail('Archived repair changed. Review restoration separately.','STALE_ARCHIVE')
        dates.append(old.repair_date)
        original=next(x for x in op.result['plan']['temporary_records'] if int(x['repair']['id'])==old.id)
        for w in original['withdrawals']:
            saved=db.get(Reserve,int(w['id']))
            if not saved or facts(saved)!=w:f.fail('Original reserve effect changed.','STALE_ARCHIVE')
        for j in original['journals']+row['journal_snapshots']:
            saved=db.get(Journal,int(j['entry']['id']))
            lines=db.query(Line).filter_by(journal_entry_id=int(j['entry']['id'])).order_by(Line.id).all()
            if not saved or facts(saved)!=j['entry'] or [facts(x) for x in lines]!=j['lines']:f.fail('Journal effect changed.','STALE_ARCHIVE')
        for w in row['reserve_reversals']:
            current=db.get(Reserve,int(w['id']))
            if not current or facts(current)!=w:f.fail('Reserve correction changed.','STALE_ARCHIVE')
            dates.append(current.entry_date)
        for jid in row['journal_reversals']:
            j=db.get(Journal,jid)
            if not j or j.tenant_id!=tenant:f.fail('Journal correction unavailable.','STALE_ARCHIVE')
            original=next((x for record in op.result['plan']['temporary_records'] for x in record['journals'] if int(x['entry']['id'])==j.reference_id),None)
            lines=db.query(Line).filter_by(journal_entry_id=jid).order_by(Line.id).all()
            expected=original['lines'] if original else []
            if j.reference_type!='dbn_temp_reverse' or len(lines)!=len(expected) or any(
                str(line.account_id)!=old['account_id'] or str(line.tenant_id)!=old['tenant_id'] or str(line.debit)!=old['credit'] or str(line.credit)!=old['debit']
                for line,old in zip(lines,expected)):
                f.fail('Journal correction changed.','STALE_ARCHIVE')
            dates.append(j.entry_date)
    require_open(db,tenant,dates)
    result={'replacement_operation_id':operation_id,'correction_date':str(body.correction_date),'source_plan_digest':source_digest,'original_operation':op.result}
    result['plan_digest']=financial.digest(result);return result


async def restore(db,tenant,slug,operation_id,body,key,author='internal-review'):
    financial.require_enabled();f.lock_business(db,tenant)
    request={'operation_id':operation_id,'body':body.model_dump(mode='json'),'author':author}
    prior,request_digest=financial.operation(db,tenant,slug,'temp_restore',key,request)
    if prior:return prior.result
    if not body.reviewed_existing_effects:f.fail('Review the restoration and its bookkeeping effects.','REPLACEMENT_CONFIRMATION_REQUIRED')
    plan=await restore_preview(db,tenant,slug,operation_id,body)
    if plan['plan_digest']!=body.expected_plan_digest:f.fail('Restoration facts changed. Refresh preview.','STALE_PLAN')
    corrections=[]
    for row in plan['original_operation']['corrections']:
        old=scoped_repair(db,tenant,row['repair_id'])
        old.archived_at=None;old.replaced_by_repair_id=None;old.archive_reason=None
        # Retain the operation marker: repeated replacement needs separate review.
        for w in row['reserve_reversals']:
            db.add(Reserve(tenant_id=tenant,truck_id=old.truck_id,entry_date=body.correction_date,entry_type='withdrawal',amount=Decimal(w['amount']),source_type='dbn_temp_restore',source_id=int(w['id']),description='Reviewed temporary repair restoration'))
        for jid in row['journal_reversals']:
            corrections.append(reverse_journal(db,tenant,db.get(Journal,jid),body.correction_date,'dbn_temp_restore',body.reason))
    db.flush()
    return financial.save_operation(db,tenant,slug,'temp_restore',key,request_digest,{'replacement_operation_id':operation_id,'plan':plan,'journal_restorations':corrections,'reason':body.reason,'author':author,'reviewed_at':datetime.now(timezone.utc).isoformat()})
