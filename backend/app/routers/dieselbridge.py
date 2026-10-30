"""Authenticated tenant-scoped DB-094 operator endpoints."""
from typing import Literal
from fastapi import APIRouter, Depends, Query
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
async def sync(slug: str, dry_run: bool = True, restart: bool = False, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        result = await d.sync_page(db, tenant, slug, dry_run, restart)
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
