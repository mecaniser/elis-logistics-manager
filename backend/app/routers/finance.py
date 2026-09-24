"""Versioned evidence, cash, operations and accounting API."""
import base64
import hashlib
import io
import json
import os
import zipfile
from datetime import date
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.finance_auth import accounting_tenant
from app.models.finance import FinanceEvidence, FinanceEvent, FinanceReport
from app.models.truck import Truck
from app.schemas.finance import Command, ReportRequest, MotiveRequest, ReconstructionRequest
from app.services import finance as f

router = APIRouter()


def event_json(e):
    return {'id': e.id, 'kind': e.kind, 'effective_date': e.effective_date.isoformat(), 'payload': e.payload, 'created_at': e.created_at.isoformat()}


@router.get('/context')
def context(request: Request, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    return {'tenant_id': tenant, 'currency': 'USD', 'basis': 'accrual', 'accounts': f.ACCOUNTS, 'assets': [{'id': x.id, 'name': x.name, 'type': x.vehicle_type} for x in db.query(Truck).filter_by(tenant_id=tenant).all()], 'motive_configured': bool(os.getenv(f'MOTIVE_API_KEY_TENANT_{tenant}')), 'legacy_preserved': True, 'owner_preview': bool(os.getenv('ELIS_OWNER_DASHBOARD_PREVIEW') == '1' and os.getenv('ELIS_FINANCE_LOCAL_TENANTS') and not os.getenv('APP_AUTH_USERNAME') and request.client and request.client.host in ('127.0.0.1', '::1', 'testclient')), 'home_enabled': db.query(FinanceEvent).filter_by(tenant_id=tenant, kind='activate_finance').first() is not None}


@router.post('/events')
def create_event(command: Command, idempotency_key: str = Header(..., min_length=8, max_length=160), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    try:
        e = f.append_command(db, tenant, command, idempotency_key)
        if e.kind in ('statement', 'settlement', 'bill'):
            f.auto_reconcile(db, tenant)
        db.commit()
        db.refresh(e)
        return event_json(e)
    except IntegrityError:
        db.rollback()
        f.fail('This source or idempotency key already exists. Refresh before retrying.', 'CONFLICT')
    except Exception:
        db.rollback()
        raise


@router.get('/events')
def list_events(cursor: int = 0, limit: int = Query(100, ge=1, le=500), kind: str | None = None, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    q = db.query(FinanceEvent).filter(FinanceEvent.tenant_id == tenant, FinanceEvent.sequence > cursor)
    if kind: q = q.filter(FinanceEvent.kind == kind)
    items = q.order_by(FinanceEvent.sequence).limit(limit + 1).all()
    return {'items': [event_json(e) for e in items[:limit]], 'next_cursor': items[limit - 1].sequence if len(items) > limit else None}


@router.get('/events/{event_id}')
def get_event(event_id: str, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    return event_json(f.resource(db, tenant, event_id))


@router.post('/evidence')
async def upload_evidence(file: UploadFile = File(...), source_key: str = Form(..., max_length=160), supersedes_id: str | None = Form(None), db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    content = await file.read(20 * 1024 * 1024 + 1)
    if not content or len(content) > 20 * 1024 * 1024: f.fail('Upload a non-empty file up to 20 MB.', status=400)
    digest = hashlib.sha256(content).hexdigest()
    prior = db.query(FinanceEvidence).filter_by(tenant_id=tenant, sha256=digest).first()
    if prior: return {'id': prior.id, 'duplicate': True, 'sha256': digest, 'extracted': prior.extracted}
    versions = db.query(FinanceEvidence).filter_by(tenant_id=tenant, source_key=source_key).all()
    if versions and not supersedes_id: f.fail('This source has changed. Select the evidence version it replaces.', 'AMENDMENT_REQUIRES_LINK')
    if supersedes_id:
        previous = f.evidence(db, tenant, supersedes_id)
        if previous.source_key != source_key: f.fail('Amendments must keep their source reference.')
        if any(x.supersedes_id == supersedes_id for x in versions): f.fail('The selected version has already been superseded.')
    extracted = {'status': 'needs_review'}
    if content.startswith(b'%PDF'):
        import pdfplumber
        try:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                pages = [{'page': i + 1, 'text': p.extract_text() or ''} for i, p in enumerate(pdf.pages)]
            extracted['pages'] = pages
            text = '\n'.join(p['text'] for p in pages)
            if '77 Cargo' in text or '77 CARGO' in text:
                from app.utils.pdf_parser import _parse_77_cargo_pdf, _extract_77_cargo_load_rows, _extract_77_cargo_sections
                parsed = _parse_77_cargo_pdf(text)
                extracted['settlement'] = json.loads(json.dumps(parsed, default=str))
                extracted['load_rows'] = _extract_77_cargo_load_rows(text)
                extracted['fuel_sections'] = _extract_77_cargo_sections(text, 'Fuel')
                from app.services.settlement_evidence import normalize_77
                extracted['proposal'] = normalize_77(text)
        except Exception as exc:
            extracted['error'] = f'Extraction requires review: {type(exc).__name__}'
    e = FinanceEvidence(tenant_id=tenant, sha256=digest, filename=(file.filename or 'document')[:255], media_type=file.content_type or 'application/octet-stream', content_base64=base64.b64encode(content).decode(), source_key=source_key, supersedes_id=supersedes_id, extraction_version='elis-evidence-v1', extracted=extracted)
    db.add(e)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        f.fail('Document already imported. Refresh the evidence list.', 'CONFLICT')
    return {'id': e.id, 'duplicate': False, 'sha256': digest, 'extracted': extracted}


@router.get('/evidence')
def list_evidence(limit: int = Query(100, ge=1, le=500), cursor: str | None = None, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    q = db.query(FinanceEvidence).filter_by(tenant_id=tenant)
    if cursor: q = q.filter(FinanceEvidence.id > cursor)
    items = q.order_by(FinanceEvidence.id).limit(limit + 1).all()
    return {'items': [{'id': e.id, 'filename': e.filename, 'source_key': e.source_key, 'sha256': e.sha256, 'supersedes_id': e.supersedes_id, 'extraction_version': e.extraction_version, 'extracted': e.extracted} for e in items[:limit]], 'next_cursor': items[limit - 1].id if len(items) > limit else None}


@router.get('/evidence/{evidence_id}/original')
def original(evidence_id: str, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    e = f.evidence(db, tenant, evidence_id)
    return Response(base64.b64decode(e.content_base64), media_type='application/octet-stream', headers={'Content-Disposition': 'attachment; filename="original-document"', 'X-Content-Type-Options': 'nosniff'})


@router.get('/settlement-history')
def settlement_history(db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    from app.services.settlement_history import settlement_history as build
    return build(db, tenant)


@router.get('/reconstruction-plan')
def reconstruction_plan(db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    from app.services.reconstruction_plan import reconstruction_plan as build
    return build(db, tenant)


@router.get('/repair-history')
def repair_history(as_of: date, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    from app.services.repair_history import repair_history as build
    return build(db, tenant, as_of)


@router.get('/workspace')
def workspace(as_of: date, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    s = f.state(db, tenant, as_of)
    from app.models.repair import Repair
    repair_options = [{'id': r.id, 'asset_id': r.truck_id, 'date': r.repair_date.isoformat() if r.repair_date else None, 'description': r.title or r.description or 'Untitled repair', 'cost': f.money(r.cost) if r.cost is not None else None} for r in db.query(Repair).join(Truck, Repair.truck_id == Truck.id).filter(Truck.tenant_id == tenant).all()]
    return {'legacy_repairs': repair_options, 'as_of': as_of.isoformat(), 'policy': s['policy'], 'accounts': [{'id': k, **v} for k, v in s['accounts'].items()], 'statements': list(s['statements'].values()), 'transactions': [{**v, 'matched': k in s['matches']} for k, v in s['transactions'].items()], 'claims': [{**c, 'remaining': f.money(c['remaining']), 'credited': f.money(c.get('credited', 0))} for c in s['claims'].values()], 'reserves': [{**r, 'balance': f.money(r['balance'])} for r in s['reserves'].values()], 'capital': f.capital_schedule(db, tenant, as_of), 'owner_cash': f.cash_position(db, tenant, as_of), 'readiness': f.readiness(db, tenant, as_of), 'assignments': s['assignments'], 'settlements': s['settlements']}


@router.post('/report-runs')
def create_report(request: ReportRequest, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    f.lock_business(db, tenant)
    result = f.report(db, tenant, request.start, request.end, request.as_of)
    run = FinanceReport(tenant_id=tenant, result=result)
    db.add(run)
    db.commit()
    return {'id': run.id, **result}


@router.get('/report-runs/{report_id}')
def get_report(report_id: str, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    r = db.query(FinanceReport).filter_by(id=report_id, tenant_id=tenant).first()
    if not r: f.fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
    return {'id': r.id, **r.result}


@router.get('/report-runs/{report_id}/package')
def accountant_package(report_id: str, draft: bool = False, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    r = get_report(report_id, db, tenant)
    if not draft and r['readiness']['status'] != 'pass': f.fail('Accounting policy, source coverage and reconciliations must pass before an accountant-ready package can be created.', 'PACKAGE_BLOCKED')
    import tempfile
    import re
    out = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode='w+b')
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('report.json', json.dumps(r, indent=2))
        z.writestr('README.txt', ('DRAFT — incomplete evidence; review readiness checks.\n' if draft else 'Accountant review package.\n') + 'Accrual books and management schedules. Not a prepared or filed tax return. Tax basis and elections remain separate. All values are USD.\n')
        for section in ('trial_balance', 'general_ledger'):
            import csv
            buf = io.StringIO()
            rows = r['ledger'][section]
            if rows:
                writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            z.writestr(section + '.csv', buf.getvalue())
        for item in r.get('evidence_manifest', []):
            document = f.evidence(db, tenant, item['id'])
            safe_name = re.sub(r'[^A-Za-z0-9._-]', '_', document.filename)[:150]
            z.writestr(f'evidence/{document.id}-{safe_name}', base64.b64decode(document.content_base64))
    out.seek(0)
    def stream():
        try:
            while chunk := out.read(65536):
                yield chunk
        finally:
            out.close()
    return StreamingResponse(stream(), media_type='application/zip', headers={'Content-Disposition': f'attachment; filename="elis-{report_id}-{ "draft" if draft else "accountant"}.zip"'})


@router.get('/legacy-comparison')
def comparison(start: date, end: date, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    if end < start: f.fail('End precedes start.', status=400)
    return f.legacy_comparison(db, tenant, start, end)


@router.post('/connections/motive/fetch')
async def motive_fetch(request: MotiveRequest, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    import httpx
    if not db.query(Truck).filter_by(id=request.asset_id, tenant_id=tenant).first(): f.fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
    if not 0 <= (request.end - request.start).days <= 89: f.fail('Fetch a period of at most 90 days.', status=400)
    token = os.getenv(f'MOTIVE_API_KEY_TENANT_{tenant}')
    if not token: f.fail('Motive is not connected. Configure the business-specific read-only API key on the server.', 'CONNECTION_NOT_CONFIGURED')
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f'https://api.gomotive.com/v3/vehicle_locations/{request.vehicle_id}', params={'start_date': request.start.isoformat(), 'end_date': request.end.isoformat(), 'updated_after': request.updated_after}, headers={'X-API-Key': token, 'X-Metric-Units': 'false'})
        if response.status_code != 200: f.fail(f'Motive returned HTTP {response.status_code}. Check connection access and retry.', 'PROVIDER_ERROR', 502)
        content = response.content
        if len(content) > 20 * 1024 * 1024: f.fail('Motive result is too large; use a shorter interval.')
        raw = response.json()
    except (httpx.HTTPError, ValueError):
        f.fail('Motive could not be reached or returned an invalid response.', 'PROVIDER_ERROR', 502)
    checksum = hashlib.sha256(content).hexdigest()
    existing = db.query(FinanceEvidence).filter_by(tenant_id=tenant, sha256=checksum).first()
    if existing: return {'evidence_id': existing.id, 'duplicate': True, 'extracted': existing.extracted}
    rows = raw.get('vehicle_locations', []) if isinstance(raw, dict) else []
    normalized = [r.get('vehicle_location', r) for r in rows if isinstance(r, dict)]
    extracted = {'status': 'needs_review', 'asset_id': request.asset_id, 'vehicle_id': request.vehicle_id, 'start': request.start.isoformat(), 'end': request.end.isoformat(), 'locations': normalized, 'note': 'Review vehicle mapping, interval coverage, odometer resets and pagination before accepting distance. Fuel tank levels alone do not establish consumption.'}
    doc = FinanceEvidence(tenant_id=tenant, sha256=checksum, filename=f'motive-{request.vehicle_id}-{request.start}-{request.end}.json', media_type='application/json', content_base64=base64.b64encode(content).decode(), source_key=f'motive:{request.vehicle_id}:{request.start}:{request.end}:{checksum[:12]}', extraction_version='motive-v3-raw-v1', extracted=extracted)
    db.add(doc)
    db.commit()
    return {'evidence_id': doc.id, 'duplicate': False, 'extracted': extracted}


@router.post('/reconstruction')
async def reconstruct(request: ReconstructionRequest, db: Session = Depends(get_db), tenant: int = Depends(accounting_tenant)):
    """Preserve legacy source originals as review candidates, never silently post history."""
    from pathlib import Path
    from urllib.parse import urlsplit
    import httpx
    from app.models.settlement import Settlement
    results = []
    root = Path(__file__).resolve().parents[2] / 'uploads'
    for legacy_id in request.legacy_ids:
        record = db.query(Settlement).join(Truck, Settlement.truck_id == Truck.id).filter(Settlement.id == legacy_id, Truck.tenant_id == tenant, Settlement.source_settlement_id.is_(None)).first()
        if not record: f.fail('Resource not found.', 'RESOURCE_NOT_FOUND', 404)
        path = record.pdf_file_path
        if not path:
            results.append({'legacy_id': legacy_id, 'status': 'gap', 'message': 'Original settlement PDF is missing.'}); continue
        try:
            parsed = urlsplit(path)
            if parsed.scheme:
                if parsed.scheme != 'https' or parsed.hostname != 'res.cloudinary.com' or parsed.port or parsed.username:
                    results.append({'legacy_id': legacy_id, 'status': 'gap', 'message': 'Re-upload this source to preserve its original safely.'}); continue
                async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
                    async with client.stream('GET', path) as response:
                        response.raise_for_status()
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            content.extend(chunk)
                            if len(content) > 20 * 1024 * 1024: raise ValueError('File exceeds 20 MB.')
                content = bytes(content)
            else:
                relative = path.split('/uploads/', 1)[-1] if '/uploads/' in path else Path(path).name
                resolved = (root / relative).resolve()
                resolved.relative_to(root.resolve())
                if resolved.stat().st_size > 20 * 1024 * 1024: raise ValueError('File exceeds 20 MB.')
                content = resolved.read_bytes()
            uploaded = await upload_evidence(UploadFile(filename=f'legacy-settlement-{legacy_id}.pdf', file=io.BytesIO(content)), f'legacy-settlement:{legacy_id}', None, db, tenant)
            results.append({'legacy_id': legacy_id, 'status': 'preserved_for_review', 'evidence_id': uploaded['id'], 'duplicate': uploaded['duplicate']})
        except (httpx.HTTPError, OSError, ValueError):
            results.append({'legacy_id': legacy_id, 'status': 'gap', 'message': 'Original could not be retrieved. Upload the original document.'})
    return {'results': results, 'posted': 0, 'note': 'Originals preserved for review. No historical accounting interpretation was overwritten.'}
