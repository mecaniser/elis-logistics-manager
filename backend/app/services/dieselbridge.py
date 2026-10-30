"""Read-only DieselBridge client and transactional review staging.

Helpers only flush. HTTP handlers own commits. Credentials live in server env.
"""
import base64
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit, quote
import httpx
from app.models.dieselbridge import DieselBridgeConnection as Connection, DieselBridgeInvoice as Invoice
from app.models.truck import Truck
from app.models.repair import Repair
from app.models.finance import FinanceEvidence
from app.services import finance as f

UTC = timezone.utc
EPOCH = '1970-01-01T00:00:00+00:00'


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None: raise ValueError()
        return result.astimezone(UTC)
    except (ValueError, AttributeError, TypeError):
        f.fail('Invalid source timestamp.', 'SOURCE_PROTOCOL_ERROR', 502)


def configs(tenant):
    try:
        entries = json.loads(os.getenv('ELIS_DIESELBRIDGE_CONNECTIONS', '[]'))
        if not isinstance(entries, list): raise ValueError()
        return [c for c in entries if c['tenant_id'] == tenant]
    except (ValueError, TypeError, KeyError):
        f.fail('DieselBridge configuration is invalid.', 'CONNECTION_NOT_CONFIGURED', 503)


def config(tenant, slug):
    entries = [c for c in configs(tenant) if c.get('slug') == slug]
    if len(entries) != 1: f.fail('Connection not found.', 'RESOURCE_NOT_FOUND', 404)
    c = entries[0]
    try:
        url = urlsplit(c['base_url'])
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ('', '/')): raise ValueError()
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}', slug): raise ValueError()
        if not c['shop_id'] or not c['bill_to_id'] or not c['api_key_env']: raise ValueError()
    except (KeyError, ValueError, TypeError):
        f.fail('DieselBridge configuration is invalid.', 'CONNECTION_NOT_CONFIGURED', 503)
    return c


def connection(db, tenant, c):
    row = db.query(Connection).filter_by(tenant_id=tenant, slug=c['slug']).first()
    if row:
        if (row.shop_id, row.bill_to_id, row.base_url) != (str(c['shop_id']), str(c['bill_to_id']), c['base_url'].rstrip('/')):
            f.fail('Connection scope changed. Reconcile and provision a separate connection.', 'CONNECTION_SCOPE_CHANGED')
        return row
    # Do not allow aliases to create competing cursor streams for a bill-to.
    if db.query(Connection).filter_by(tenant_id=tenant, shop_id=str(c['shop_id']), bill_to_id=str(c['bill_to_id'])).first():
        f.fail('This bill-to already has a connection.', 'CONNECTION_SCOPE_CHANGED')
    return Connection(tenant_id=tenant, slug=c['slug'], shop_id=str(c['shop_id']), bill_to_id=str(c['bill_to_id']), base_url=c['base_url'].rstrip('/'))


def normalize_vin(value):
    return re.sub(r'\s+', '', value or '').upper()


def match(db, tenant, vin):
    vin = normalize_vin(vin)
    if not vin: return None, 'missing_vin'
    assets = [t for t in db.query(Truck).filter_by(tenant_id=tenant).all() if normalize_vin(t.vin) == vin]
    trucks = [t for t in assets if t.vehicle_type == 'truck']
    if len(trucks) > 1: return None, 'duplicate_vin'
    if not trucks: return None, 'vehicle_type_mismatch' if assets else 'unmatched_vin'
    return trucks[0].id, 'cost_treatment_required'


def resource(db, tenant, invoice_id):
    row = db.query(Invoice).filter_by(id=invoice_id, tenant_id=tenant).first()
    if not row: f.fail('Invoice not found.', 'RESOURCE_NOT_FOUND', 404)
    return row


def validate_item(item, c):
    if not isinstance(item, dict): f.fail('Invalid invoice.', 'SOURCE_PROTOCOL_ERROR', 502)
    for key in ('shop_id', 'invoice_id', 'effective_updated_at'):
        if not isinstance(item.get(key), str) or not item[key] or len(item[key]) > 80:
            f.fail('Invalid invoice identity.', 'SOURCE_PROTOCOL_ERROR', 502)
    if item['shop_id'] != str(c['shop_id']): f.fail('Source shop differs from configured scope.', 'SOURCE_SCOPE_ERROR', 502)
    timestamp(item['effective_updated_at'])
    kind = item.get('event_type', 'invoice')
    if kind == 'access_removed':
        if not isinstance(item.get('event_id'), str) or not item['event_id'] or len(item['event_id']) > 80:
            f.fail('Invalid removal event.', 'SOURCE_PROTOCOL_ERROR', 502)
    elif kind == 'invoice':
        try:
            if item['currency'] != 'USD' or item['status'] not in ('sent', 'paid', 'overdue', 'cancelled'):
                raise ValueError()
            if not isinstance(item['total_amount'], str): raise ValueError()
            amount = Decimal(item['total_amount'])
            if not amount.is_finite() or amount < 0 or amount >= Decimal('100000000') or amount.as_tuple().exponent < -2: raise ValueError()
            date.fromisoformat(item['invoice_date'])
            if item.get('vin') is not None and not isinstance(item['vin'], str): raise ValueError()
        except (KeyError, TypeError, ValueError, InvalidOperation):
            f.fail('Invalid finalized invoice.', 'SOURCE_PROTOCOL_ERROR', 502)
    else: f.fail('Unknown source event.', 'SOURCE_PROTOCOL_ERROR', 502)
    return kind


def stage(db, tenant, c, item):
    kind = validate_item(item, c)
    revision = timestamp(item['effective_updated_at']).isoformat()
    row = db.query(Invoice).filter_by(tenant_id=tenant, source_system='dieselbridge', shop_id=item['shop_id'], invoice_id=item['invoice_id']).first()
    if row and row.bill_to_id != str(c['bill_to_id']):
        f.fail('Invoice bill-to changed. Reconcile the prior connection first.', 'INVOICE_SCOPE_CONFLICT')
    if row:
        old = timestamp(row.revision)
        if timestamp(revision) < old: return row
        if timestamp(revision) == old:
            if kind == 'access_removed' and row.state != 'access_removed': pass  # removal wins ties
            elif row.payload == item: return row
            elif row.state == 'access_removed': return row
            else: f.fail('Source changed without a new revision.', 'SOURCE_REVISION_CONFLICT', 502)
    else:
        row = Invoice(tenant_id=tenant, source_system='dieselbridge', shop_id=item['shop_id'], invoice_id=item['invoice_id'], bill_to_id=str(c['bill_to_id']))
        db.add(row)
    row.revision, row.event_id, row.payload = revision, item.get('event_id'), item
    if kind == 'access_removed':
        row.state, row.review_reason = 'access_removed', 'access_review_required'
    else:
        matched, reason = match(db, tenant, item.get('vin'))
        if row.truck_id is None: row.truck_id = matched
        elif matched != row.truck_id: reason = 'truck_identity_changed'
        if item.get('voided_at') or item['status'] in ('cancelled', 'voided'): reason = 'void_or_cancellation'
        elif item.get('supersedes_invoice_id'): reason = 'replacement_invoice'
        if row.repair_id:
            row.state, row.review_reason = 'correction_required', reason if reason != 'cost_treatment_required' else 'source_revision_changed'
        else:
            row.state, row.review_reason = 'review_required', reason
        previous = item.get('supersedes_invoice_id')
        if previous:
            prior = db.query(Invoice).filter_by(tenant_id=tenant, source_system='dieselbridge', shop_id=item['shop_id'], invoice_id=previous).first()
            if prior:
                prior.state, prior.review_reason = 'correction_required', 'superseded_invoice'
    # A replacement may have arrived before its older source invoice.
    if any(i.payload.get('supersedes_invoice_id') == row.invoice_id for i in db.query(Invoice).filter_by(tenant_id=tenant, shop_id=row.shop_id).all() if i.id != row.id):
        if row.state != 'access_removed':
            row.state, row.review_reason = 'correction_required', 'superseded_invoice'
    db.flush()
    return row


class SourceClient:
    def __init__(self, c):
        self.c = c
        self.key = os.getenv(c['api_key_env'])
        if not self.key: f.fail('Configure the connection credential on the server.', 'CONNECTION_NOT_CONFIGURED', 503)

    async def request(self, path, params=None):
        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=30) as client:
                response = await client.get(self.c['base_url'].rstrip('/') + '/api/v1/fleet-invoice-exports/' + path, params=params, headers={'X-API-Key': self.key})
        except httpx.RequestError:
            f.fail('DieselBridge is unavailable. Retry this page.', 'SOURCE_UNAVAILABLE', 502)
        if response.status_code == 401: f.fail('DieselBridge credential is invalid or revoked.', 'SOURCE_UNAUTHORIZED', 502)
        if response.status_code == 404: f.fail('Source document unavailable.', 'RESOURCE_NOT_FOUND', 404)
        if response.status_code != 200: f.fail('DieselBridge rejected the request. Sync progress was retained.', 'SOURCE_REQUEST_FAILED', 502)
        return response

    async def page(self, params):
        response = await self.request('invoices', params)
        try: return response.json()
        except ValueError: f.fail('Invalid source response.', 'SOURCE_PROTOCOL_ERROR', 502)

    async def pdf(self, invoice_id):
        response = await self.request('invoices/' + quote(invoice_id, safe='') + '/pdf')
        if not response.content.startswith(b'%PDF') or len(response.content) > 20 * 1024 * 1024:
            f.fail('Invalid source PDF.', 'SOURCE_PROTOCOL_ERROR', 502)
        return response.content


async def sync_page(db, tenant, slug, dry_run=False, restart=False):
    f.lock_business(db, tenant)
    c = config(tenant, slug)
    row = connection(db, tenant, c)
    before = (row.window_before if not restart else None) or datetime.now(UTC).isoformat()
    since = (row.window_since if not restart else None) or ((timestamp(row.watermark) - timedelta(days=1)).isoformat() if row.watermark else EPOCH)
    params = {'updated_since': since, 'updated_before': before, 'limit': 100}
    if row.cursor and not restart: params['cursor'] = row.cursor
    page = await SourceClient(c).page(params)
    if (not isinstance(page, dict) or not isinstance(page.get('items'), list) or len(page['items']) > 100
            or timestamp(page.get('watermark')) != timestamp(before)
            or (page.get('next_cursor') is not None and (not isinstance(page['next_cursor'], str) or not page['next_cursor'] or page['next_cursor'] == row.cursor))):
        f.fail('Invalid source page.', 'SOURCE_PROTOCOL_ERROR', 502)
    for item in page['items']:
        validate_item(item, c)
        if not timestamp(since) <= timestamp(item['effective_updated_at']) < timestamp(before):
            f.fail('Source revision outside sync window.', 'SOURCE_PROTOCOL_ERROR', 502)
    if dry_run:
        return {'dry_run': True, 'items': [{'invoice_id': i['invoice_id'], 'event_type': i.get('event_type', 'invoice'), 'match': match(db, tenant, i.get('vin'))[1]} for i in page['items']], 'has_more': bool(page.get('next_cursor')), 'watermark': row.watermark}
    db.add(row)
    for item in page['items']: stage(db, tenant, c, item)
    if page.get('next_cursor'):
        row.window_since, row.window_before, row.cursor = since, before, page['next_cursor']
    else:
        row.watermark, row.window_since, row.window_before, row.cursor = before, None, None, None
    db.flush()
    return {'dry_run': False, 'applied': len(page['items']), 'has_more': bool(row.cursor), 'watermark': row.watermark}


def accept(db, tenant, invoice_id, revision, note):
    f.lock_business(db, tenant)
    row = resource(db, tenant, invoice_id)
    if row.revision != revision: f.fail('Invoice changed. Refresh before accepting.', 'STALE_INVOICE')
    if row.repair_id:
        if row.state == 'accepted' and row.accepted_revision == revision: return row
        f.fail('An existing repair requires explicit correction.', 'CORRECTION_REQUIRED')
    # The old invoice-only flow cannot resolve a conditional card surcharge.
    # Route new costs through the settlement-aware importer; retain idempotent
    # access to already accepted historical records above.
    # Explicitly present fee data must be a canonical known zero. Missing
    # fields remain compatible with older fee-free staging fixtures; malformed
    # or conditional fee values must never fall through as zero.
    if 'service_fee_amount' in row.payload and row.payload['service_fee_amount'] != '0.00':
        f.fail('Use the settlement-aware repair import to distinguish quoted card fees from actual repair cost.', 'SETTLEMENT_IMPORT_REQUIRED')
    from app.models.dieselbridge import DieselBridgeRepairLink
    managed = db.query(DieselBridgeRepairLink).filter_by(tenant_id=tenant, shop_id=row.shop_id).all()
    if any(link.repair_order_id == row.payload.get('repair_order_id') or link.accepted_invoice_id == row.invoice_id for link in managed):
        f.fail('This repair order already has a canonical financial repair. Use its source review.', 'EXISTING_REPAIR_SOURCE_REVIEW')
    if row.state == 'access_removed': f.fail('Source access requires review.', 'REVIEW_REQUIRED')
    # Re-evaluate on owner action: trucks can be added or their VINs changed.
    matched, reason = match(db, tenant, row.payload.get('vin'))
    if row.truck_id and matched != row.truck_id: reason = 'truck_identity_changed'
    if reason != 'cost_treatment_required' or row.review_reason in ('void_or_cancellation', 'replacement_invoice', 'superseded_invoice'):
        f.fail('Resolve vehicle, cancellation or replacement review first.', 'REVIEW_REQUIRED')
    item = row.payload
    if item.get('invoice_number') and db.query(Repair).join(Truck, Repair.truck_id == Truck.id).filter(Truck.tenant_id == tenant, Repair.invoice_number == item['invoice_number']).first():
        f.fail('An existing repair has this invoice number. Reconcile it before accepting.', 'EXISTING_REPAIR_REVIEW')
    snapshot = item.get('line_items') or {}
    lines = []
    if isinstance(snapshot, dict):
        for kind, label in (('labor', 'Labor'), ('parts', 'Part')):
            for entry in snapshot.get(kind, []) or []:
                if isinstance(entry, dict) and entry.get('description'):
                    lines.append(f"{label}: {entry['description']}")
    repair = Repair(truck_id=matched, repair_date=date.fromisoformat(item['invoice_date']), title='DieselBridge invoice ' + str(item.get('invoice_number') or item['invoice_id'])[:160], details='\n'.join(lines) or None, invoice_number=item.get('invoice_number'), cost=Decimal(item['total_amount']), miles=None, paid_from_reserve=False, category='maintenance')
    db.add(repair); db.flush()
    row.truck_id, row.repair_id, row.accepted_revision = matched, repair.id, revision
    row.state, row.review_reason, row.review_note = 'accepted', 'owner_confirmed_repair_cost', note
    content = json.dumps({'source': item, 'review_note': note, 'cost_treatment': 'repair_expense'}, sort_keys=True).encode()
    db.add(FinanceEvidence(tenant_id=tenant, sha256=hashlib.sha256(content).hexdigest(), filename=f'dieselbridge-{row.id}.json', media_type='application/json', content_base64=base64.b64encode(content).decode(), source_key=f'dieselbridge:{row.shop_id}:{row.invoice_id}', extraction_version='dieselbridge-invoice-v1', extracted={'legacy_repair_ids': [repair.id], 'invoice_review': {'source_total': item['total_amount']}, 'payment_basis': 'not_established', 'source': item, 'review_note': note}))
    db.flush()
    return row


def public(row):
    return {'id': row.id, 'shop_id': row.shop_id, 'invoice_id': row.invoice_id, 'revision': row.revision, 'truck_id': row.truck_id, 'repair_id': row.repair_id, 'state': row.state, 'review_reason': row.review_reason, 'accepted_revision': row.accepted_revision, 'invoice': row.payload}
