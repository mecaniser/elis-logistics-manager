"""Authenticated tenant-scoped DB-094 operator endpoints."""
import asyncio
from typing import Literal
from fastapi import APIRouter, Depends, Query, Header
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.finance_auth import accounting_tenant
from app.models.dieselbridge import DieselBridgeConnection as Connection, DieselBridgeInvoice as Invoice
from app.services import dieselbridge as d

router = APIRouter()


class Acceptance(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    revision: str = Field(min_length=1, max_length=40)
    cost_treatment: Literal['repair_expense']
    note: str = Field(min_length=3, max_length=2000)


@router.get('/connections')
def connections(db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    rows = {r.slug: r for r in db.query(Connection).filter_by(tenant_id=tenant).all()}
    return {'items': [{'slug': c['slug'], 'shop_id': str(c['shop_id']), 'bill_to_id': str(c['bill_to_id']), 'watermark': rows[c['slug']].watermark if c['slug'] in rows else None, 'has_more': bool(rows[c['slug']].cursor) if c['slug'] in rows else False} for c in d.configs(tenant)]}


@router.post('/connections/{slug}/sync')
def sync(slug: str, dry_run: bool = True, restart: bool = False, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        # Keep the blocking tenant lock and its HTTP wait on a worker thread.
        result = asyncio.run(d.sync_page(db, tenant, slug, dry_run, restart))
        if dry_run: db.rollback()
        else: db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.get('/invoices')
def invoices(truck_id: int | None = None, limit: int = Query(100, ge=1, le=500), after: int = Query(0, ge=0), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    q = db.query(Invoice).filter(Invoice.tenant_id == tenant, Invoice.id > after)
    if truck_id is not None:
        if not db.query(d.Truck).filter_by(id=truck_id, tenant_id=tenant).first(): d.f.fail('Truck not found.', 'RESOURCE_NOT_FOUND', 404)
        q = q.filter(Invoice.truck_id == truck_id)
    rows = q.order_by(Invoice.id).limit(limit + 1).all()
    return {'items': [d.public(r) for r in rows[:limit]], 'next_after': rows[limit - 1].id if len(rows) > limit else None}


@router.post('/invoices/{invoice_id}/accept')
def accept(invoice_id: int, body: Acceptance, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        row = d.accept(db, tenant, invoice_id, body.revision, body.note)
        db.commit()
        return d.public(row)
    except Exception:
        db.rollback()
        raise


@router.get('/invoices/{invoice_id}/pdf')
async def pdf(invoice_id: int, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    row = d.resource(db, tenant, invoice_id)
    if row.state == 'access_removed': d.f.fail('Source unavailable.', 'RESOURCE_NOT_FOUND', 404)
    candidates = [c for c in d.configs(tenant) if str(c['shop_id']) == row.shop_id and str(c['bill_to_id']) == row.bill_to_id]
    if len(candidates) != 1: d.f.fail('Source unavailable.', 'RESOURCE_NOT_FOUND', 404)
    c = d.config(tenant, candidates[0]['slug'])
    d.connection(db, tenant, c)
    content = await d.SourceClient(c).pdf(row.invoice_id)
    return Response(content, media_type='application/pdf', headers={'Cache-Control': 'private, no-store', 'Content-Disposition': 'inline; filename=invoice.pdf'})


@router.get('/repair-history')
def repair_order_history(truck_id: int | None = None, limit: int = Query(100, ge=1, le=500), after: int = Query(0, ge=0), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    from app.models.dieselbridge import DieselBridgeRepairHistory
    query = db.query(DieselBridgeRepairHistory).filter(DieselBridgeRepairHistory.tenant_id == tenant)
    if truck_id is not None:
        if not db.query(d.Truck).filter_by(id=truck_id, tenant_id=tenant).first():
            d.f.fail('Truck not found.', 'RESOURCE_NOT_FOUND', 404)
        query = query.filter(DieselBridgeRepairHistory.truck_id == truck_id)
    total = query.count()
    rows = query.filter(DieselBridgeRepairHistory.id > after).order_by(DieselBridgeRepairHistory.id).limit(limit + 1).all()
    from app.services.dieselbridge_repair_history import public
    return {'items': [public(db, tenant, row) for row in rows[:limit]], 'total': total, 'next_after': rows[limit - 1].id if len(rows) > limit else None}


@router.post('/connections/{slug}/repair-history/sync')
def sync_repair_order_history(slug: str, dry_run: bool = True, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    from app.services.dieselbridge_repair_history import sync_history
    try:
        result = asyncio.run(sync_history(db, tenant, slug, dry_run))
        if dry_run:
            db.rollback()
        else:
            db.commit()
        return result
    except Exception:
        db.rollback()
        raise


from app.schemas.dieselbridge_financial import FinancialSelection, FinancialSync, VerifiedRepairPayment, RepairPaymentReversal, SourceReviewPreview, SourceReviewApply
from app.services import dieselbridge_financial as financial


@router.post('/connections/{slug}/financial-import/preview')
def financial_preview(slug: str, body: FinancialSelection, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        result = asyncio.run(financial.preview_financial(db, tenant, slug, body.repair_order_ids))
        db.rollback()
        return result
    except Exception:
        db.rollback(); raise


@router.post('/connections/{slug}/financial-import/sync')
def financial_sync(slug: str, body: FinancialSync, key: str = Header(alias='Idempotency-Key', min_length=1, max_length=160), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        result = asyncio.run(financial.sync_financial(db, tenant, slug, repair_order_ids=body.repair_order_ids,
            expected_plan_digest=body.expected_plan_digest, idempotency_key=key))
        db.commit(); return result
    except Exception:
        db.rollback(); raise


@router.get('/repair-financial-states')
def financial_states(db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    from app.models.dieselbridge import DieselBridgeRepairLink
    from app.models.repair import Repair
    rows = db.query(DieselBridgeRepairLink).join(Repair, Repair.id == DieselBridgeRepairLink.repair_id).filter(DieselBridgeRepairLink.tenant_id == tenant).order_by(DieselBridgeRepairLink.id).all()
    return {'items': [{'repair_id': r.repair_id, **financial.public_state(db, tenant, r)} for r in rows]}


@router.get('/repairs/{repair_id}/financial-state')
def financial_state(repair_id: int, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    return financial.public_state(db, tenant, financial.scoped_link(db, tenant, repair_id))


@router.post('/repairs/{repair_id}/verified-payments')
def verified_repair_payment(repair_id: int, body: VerifiedRepairPayment, key: str = Header(alias='Idempotency-Key', min_length=1, max_length=160), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        result = financial.record_verified_payment(db, tenant, repair_id, body, key)
        db.commit(); return result
    except Exception:
        db.rollback(); raise


@router.post('/repairs/{repair_id}/payments/{payment_id}/reverse')
def reverse_repair_payment(repair_id: int, payment_id: int, body: RepairPaymentReversal, key: str = Header(alias='Idempotency-Key', min_length=1, max_length=160), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        result = financial.reverse_verified_payment(db, tenant, repair_id, payment_id, body, key)
        db.commit(); return result
    except Exception:
        db.rollback(); raise


@router.get('/repairs/{repair_id}/source-pdf')
async def financial_source_pdf(repair_id: int, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    link = financial.scoped_link(db, tenant, repair_id)
    if link.state == 'access_removed': d.f.fail('Source document unavailable.', 'RESOURCE_NOT_FOUND', 404)
    config = d.config(tenant, link.slug)
    d.connection(db, tenant, config)
    if (link.shop_id, link.customer_id) != (str(config['shop_id']), str(config['bill_to_id'])):
        d.f.fail('Source document unavailable.', 'RESOURCE_NOT_FOUND', 404)
    content = await d.SourceClient(config).pdf(link.accepted_invoice_id)
    expected = link.accepted_payload['invoice'].get('pdf_sha256')
    if expected and financial.hashlib.sha256(content).hexdigest() != expected:
        d.f.fail('Preserved invoice PDF changed. Review the document.', 'SOURCE_DOCUMENT_CHANGED', 502)
    return Response(content, media_type='application/pdf', headers={'Cache-Control':'private, no-store', 'Content-Disposition':'inline; filename=invoice.pdf'})


@router.post('/repairs/{repair_id}/source-review/preview')
def source_review_preview(repair_id: int, body: SourceReviewPreview, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        result,_,_,_ = asyncio.run(financial.review_preview(db, tenant, repair_id, body.expected_revision))
        db.rollback(); return result
    except Exception:
        db.rollback(); raise


@router.post('/repairs/{repair_id}/source-review/apply')
def source_review_apply(repair_id: int, body: SourceReviewApply, key: str = Header(alias='Idempotency-Key', min_length=1, max_length=160), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        result = asyncio.run(financial.apply_source_review(db, tenant, repair_id, body, key))
        db.commit(); return result
    except Exception:
        db.rollback(); raise


@router.get('/repairs/{repair_id}/source-review/pdf')
async def source_review_pdf(repair_id: int, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    link = financial.scoped_link(db, tenant, repair_id)
    config = d.config(tenant, link.slug)
    d.connection(db, tenant, config)
    if (link.shop_id,link.customer_id) != (str(config['shop_id']),str(config['bill_to_id'])):
        d.f.fail('Source document unavailable.','RESOURCE_NOT_FOUND',404)
    value = await financial.manifest(config)
    row = next((r for r in value['items'] if r['repair_order_id']==link.repair_order_id),None)
    if not row or row['authorization']!='authorized':d.f.fail('Source document unavailable.','RESOURCE_NOT_FOUND',404)
    inv=row['invoice'];content=await d.SourceClient(config).pdf(inv['invoice_id'])
    if inv['pdf_sha256'] and financial.hashlib.sha256(content).hexdigest()!=inv['pdf_sha256']:
        d.f.fail('Preserved invoice PDF changed. Review the document.','SOURCE_DOCUMENT_CHANGED',502)
    return Response(content,media_type='application/pdf',headers={'Cache-Control':'private, no-store','Content-Disposition':'inline; filename=invoice.pdf'})


from app.schemas.dieselbridge_financial import ReconciliationNoteInput
from app.services import dieselbridge_reconciliation as reconciliation
import os


def _note_author():
    # accounting_tenant already verifies this exact configured principal.
    return os.getenv('APP_AUTH_USERNAME') or 'local-development'


@router.get('/connections/{slug}/repair-orders/{repair_order_id}/reconciliation-notes')
def source_reconciliation_notes(slug: str, repair_order_id: str, after: int = Query(0,ge=0), limit: int = Query(100,ge=1,le=100), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    return reconciliation.page(db,tenant,slug,repair_order_id,after,limit)


@router.post('/connections/{slug}/repair-orders/{repair_order_id}/reconciliation-notes')
def append_source_reconciliation_note(slug: str, repair_order_id: str, body: ReconciliationNoteInput, key: str = Header(alias='Idempotency-Key',min_length=1,max_length=160), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        result=reconciliation.append(db,tenant,slug,repair_order_id,body,key,_note_author())
        db.commit();return result
    except Exception:
        db.rollback();raise


@router.get('/repairs/{repair_id}/reconciliation-notes')
def repair_reconciliation_notes(repair_id: int, after: int = Query(0,ge=0), limit: int = Query(100,ge=1,le=100), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    link=financial.scoped_link(db,tenant,repair_id)
    return reconciliation.page(db,tenant,link.slug,link.repair_order_id,after,limit)


@router.post('/repairs/{repair_id}/reconciliation-notes')
def append_repair_reconciliation_note(repair_id: int, body: ReconciliationNoteInput, key: str = Header(alias='Idempotency-Key',min_length=1,max_length=160), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        link=financial.scoped_link(db,tenant,repair_id)
        result=reconciliation.append(db,tenant,link.slug,link.repair_order_id,body,key,_note_author())
        db.commit();return result
    except Exception:
        db.rollback();raise
