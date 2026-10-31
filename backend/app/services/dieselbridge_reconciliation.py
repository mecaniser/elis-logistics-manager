"""Append-only notes and explicit source-bound occurrence decisions; no payment inference."""
from datetime import datetime, timezone
from app.models.dieselbridge import DieselBridgeRepairHistory, DieselBridgeRepairLink
from app.models.dieselbridge_reconciliation import DieselBridgeReconciliationNote as Note
from app.services import dieselbridge as d
from app.services import finance as f
from app.services.dieselbridge_financial import digest


def scope(db,tenant,slug,repair_order_id):
    config=d.config(tenant,slug)
    pinned=d.connection(db,tenant,config)
    identity=dict(tenant_id=tenant,slug=slug,shop_id=str(config['shop_id']),customer_id=str(config['bill_to_id']),repair_order_id=repair_order_id)
    known=db.query(DieselBridgeRepairLink).filter_by(**identity).first()
    if not known:
        known=db.query(DieselBridgeRepairHistory).filter_by(tenant_id=tenant,shop_id=identity['shop_id'],customer_id=identity['customer_id'],repair_order_id=repair_order_id).first()
    if not known:f.fail('Repair order not found.','RESOURCE_NOT_FOUND',404)
    return identity,pinned


def public(row):
    return {'id':row.id,'repair_order_id':row.repair_order_id,'note':row.note,'source_references':row.source_references,
        'confirmed_service_date':row.confirmed_service_date.isoformat() if row.confirmed_service_date else None,
        'date_treatment':row.date_treatment,'source_revision':row.source_revision,
        'original_invoice_date':row.original_invoice_date.isoformat() if row.original_invoice_date else None,
        'amount_discrepancy':row.amount_discrepancy,'supersedes_note_id':row.supersedes_note_id,'author':row.author,'created_at':row.created_at}


def append(db,tenant,slug,repair_order_id,body,key,author):
    f.lock_business(db,tenant)
    identity,pinned=scope(db,tenant,slug,repair_order_id)
    if not isinstance(key,str) or not 1<=len(key)<=160:f.fail('Supply an Idempotency-Key.','IDEMPOTENCY_KEY_REQUIRED',422)
    request_body=body.model_dump(mode='json')
    if body.date_treatment=='note_only' and not body.expected_source_revision:
        request_body.pop('date_treatment');request_body.pop('expected_source_revision')
    request_digest=digest({'scope':identity,'body':request_body,'author':author})
    prior=db.query(Note).filter_by(**identity,key=key).first()
    if prior:
        if prior.request_digest!=request_digest:f.fail('Idempotency key was already used with different content.','IDEMPOTENCY_CONFLICT')
        return public(prior)
    if body.supersedes_note_id:
        previous=db.query(Note).filter_by(**identity,id=body.supersedes_note_id).first()
        if previous and previous.date_treatment!='note_only' and body.date_treatment=='note_only':
            f.fail('Correct a date decision with an explicit date treatment; append narrative separately.','DATE_DECISION_EVIDENCE_REQUIRED',422)
        if not previous:f.fail('Correction must reference a note on this repair order.','INVALID_NOTE_CORRECTION')
        if db.query(Note).filter_by(supersedes_note_id=previous.id).first():
            f.fail('This note already has a correction. Correct its latest replacement.','NOTE_ALREADY_CORRECTED')
    values=body.model_dump(exclude={'expected_source_revision'})
    if body.date_treatment!='note_only':
        import asyncio
        from app.services import dieselbridge_financial as financial
        if not body.expected_source_revision or body.date_treatment=='confirmed_service_date' and not body.confirmed_service_date:
            f.fail('A reviewed service date and current source revision are required.','DATE_DECISION_EVIDENCE_REQUIRED',422)
        config=d.config(tenant,slug)
        value=asyncio.run(financial.manifest(config))
        source=next((r for r in value['items'] if r['repair_order_id']==repair_order_id),None)
        if not source or source['authorization']!='authorized':f.fail('Authorized source invoice is required.','SOURCE_ACCESS_REQUIRED')
        if source['revision']!=body.expected_source_revision:f.fail('Source changed. Refresh its preview.','STALE_INVOICE')
        previous=db.query(Note).filter_by(**identity).filter(Note.date_treatment!='note_only').order_by(Note.id.desc()).first()
        if (previous.id if previous else None)!=body.supersedes_note_id:
            f.fail('Date review changed. Correct its latest date decision.','STALE_DATE_DECISION')
        values['source_revision']=source['revision']
    elif body.expected_source_revision:
        f.fail('Choose an explicit date treatment for source-bound review.','DATE_DECISION_EVIDENCE_REQUIRED',422)
    row=Note(**identity,**values,key=key,request_digest=request_digest,author=author,
        created_at=datetime.now(timezone.utc).isoformat())
    db.add(pinned);db.add(row);db.flush()
    return public(row)


def page(db,tenant,slug,repair_order_id,after=0,limit=100):
    identity,_=scope(db,tenant,slug,repair_order_id)
    rows=db.query(Note).filter_by(**identity).filter(Note.id>after).order_by(Note.id).limit(limit+1).all()
    return {'items':[public(row) for row in rows[:limit]],'next_after':rows[limit-1].id if len(rows)>limit else None}


def for_link(db,tenant,link):
    rows=db.query(Note).filter_by(tenant_id=tenant,slug=link.slug,shop_id=link.shop_id,customer_id=link.customer_id,repair_order_id=link.repair_order_id).order_by(Note.id.desc()).limit(101).all()
    return {'reconciliation_notes':[public(row) for row in reversed(rows[:100])],'reconciliation_notes_has_older':len(rows)>100}
