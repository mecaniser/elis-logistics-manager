"""Verify signed wake-ups and process durable jobs with financial refetch.

The event never supplies an amount, invoice identity or payment fact. Helpers
receiving events only flush; the HTTP handler commits. The worker owns a single
transaction for financial sync and inbox completion, so a crash cannot create
an acknowledged-but-unbooked event. No worker starts on module import.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import or_
from app.models.dieselbridge_events import DieselBridgeFinancialInbox as Inbox
from app.models.tenant import Tenant
from app.services import dieselbridge as d
from app.services import finance as f

VERSION = 'db094-financial-wakeup-v1'
MAX_BODY_BYTES = 16384
SIGNATURE_TOLERANCE_SECONDS = 300
MAX_ATTEMPTS = 12
PAUSED_CODES = {'WEBHOOK_NOT_CONFIGURED','CONNECTION_NOT_CONFIGURED','FEATURE_DISABLED'}
FIELDS = {'version','event_id','shop_id','customer_id','repair_order_id','kind','occurred_at'}
KINDS = {'invoice_finalized','invoice_changed','invoice_cancelled'}


def utcnow():
    return datetime.now(timezone.utc)


def enabled():
    return os.getenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','').lower() in {'1','true'}


def fail(status, code, message):
    raise HTTPException(status, detail={'code':code,'message':message})


def _object(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _parse(body):
    if len(body) > MAX_BODY_BYTES:
        fail(413,'EVENT_TOO_LARGE','Notification exceeds the supported size.')
    try:
        value = json.loads(body.decode('utf-8'),object_pairs_hook=_object)
        if not isinstance(value,dict) or set(value) != FIELDS or any(not isinstance(v,str) for v in value.values()):
            raise ValueError()
        if value['version'] != VERSION or value['kind'] not in KINDS:
            raise ValueError()
        for key in ('event_id','shop_id','customer_id','repair_order_id'):
            if str(UUID(value[key])) != value[key]:
                raise ValueError()
        if len(value['occurred_at']) > 40:
            raise ValueError()
        occurred = datetime.fromisoformat(value['occurred_at'].replace('Z','+00:00'))
        if occurred.tzinfo is None or occurred.utcoffset() != timedelta(0):
            raise ValueError()
    except (ValueError, TypeError, UnicodeError, OverflowError):
        fail(400,'INVALID_EVENT','Notification does not match the supported contract.')
    return value,occurred


def _config(slug, shop, customer):
    if not isinstance(slug,str) or not re.fullmatch('[a-zA-Z0-9_-]{1,60}',slug):
        fail(401,'INVALID_EVENT_AUTH','Notification authorization failed.')
    try:
        entries = json.loads(os.getenv('ELIS_DIESELBRIDGE_CONNECTIONS','[]'))
        if not isinstance(entries,list):
            raise ValueError()
        matches = [c for c in entries if isinstance(c,dict) and c.get('slug') == slug
                   and c.get('shop_id') == shop and c.get('bill_to_id') == customer]
        if len(matches) != 1:
            fail(401,'INVALID_EVENT_AUTH','Notification authorization failed.')
        selected = matches[0]
        tenant = selected['tenant_id']
        if type(tenant) is not int or tenant <= 0:
            raise ValueError()
        config = d.config(tenant,slug)
    except (ValueError,TypeError,KeyError):
        fail(503,'WEBHOOK_NOT_CONFIGURED','Notification connection is not configured.')
    return tenant,config


def _secret(config):
    reference = config.get('event_secret_env')
    if (not isinstance(reference,str) or not re.fullmatch('[A-Z][A-Z0-9_]{0,127}',reference)
            or reference == config.get('api_key_env')):
        fail(503,'WEBHOOK_NOT_CONFIGURED','Notification verification is not configured.')
    secret = os.getenv(reference,'')
    if len(secret.encode('utf-8')) < 32 or secret == os.getenv(config['api_key_env']):
        fail(503,'WEBHOOK_NOT_CONFIGURED','Notification verification is not configured.')
    return secret


def receive_event(db, slug, body, headers, *, now=None):
    value,occurred = _parse(body)
    tenant,config = _config(slug,value['shop_id'],value['customer_id'])
    secret = _secret(config)
    normalized = {k.lower():v for k,v in headers.items()}
    event_id = normalized.get('x-dbn-event-id','')
    timestamp = normalized.get('x-dbn-timestamp','')
    signature = normalized.get('x-dbn-signature','')
    current = now or utcnow()
    if (event_id != value['event_id'] or not re.fullmatch('[0-9]{1,12}',timestamp)
            or not re.fullmatch('v1=[0-9a-f]{64}',signature)):
        fail(401,'INVALID_EVENT_AUTH','Notification authorization failed.')
    if abs(int(current.timestamp())-int(timestamp)) > SIGNATURE_TOLERANCE_SECONDS:
        fail(401,'INVALID_EVENT_AUTH','Notification authorization failed.')
    expected = 'v1='+hmac.new(secret.encode('utf-8'),timestamp.encode('ascii')+b'.'+body,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,signature):
        fail(401,'INVALID_EVENT_AUTH','Notification authorization failed.')
    if not enabled():
        fail(503,'FEATURE_DISABLED','Financial import is not enabled.')
    if not db.query(Tenant).filter_by(id=tenant,is_active=True).first():
        fail(401,'INVALID_EVENT_AUTH','Notification authorization failed.')
    # Serialize same-connection deliveries before the duplicate lookup/insert.
    f.lock_business(db,tenant)
    digest = hashlib.sha256(body).hexdigest()
    prior = db.query(Inbox).filter_by(tenant_id=tenant,slug=slug,event_id=event_id).first()
    if prior:
        if prior.body_digest != digest:
            fail(409,'EVENT_ID_CONFLICT','This notification identity has different content.')
        return {'status':'queued','event_id':event_id,'duplicate':True}
    row = Inbox(tenant_id=tenant,slug=slug,event_id=event_id,body_digest=digest,
        shop_id=value['shop_id'],customer_id=value['customer_id'],repair_order_id=value['repair_order_id'],
        event_kind=value['kind'],payload=value,occurred_at=occurred,received_at=current,status='pending',attempts=0)
    db.add(row);db.flush()
    return {'status':'queued','event_id':event_id,'duplicate':False}


def _error_code(exc):
    detail = getattr(exc,'detail',None)
    code = detail.get('code') if isinstance(detail,dict) else None
    return code if isinstance(code,str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',code) else 'FINANCIAL_SYNC_FAILED'


async def process_pending_once(session_factory, *, sync_fn=None, now=None):
    """Run one job on an operator/worker thread, not the HTTP event loop."""
    if not enabled():
        return {'processed':0,'status':'disabled'}
    current = now or utcnow()
    row_id = None
    try:
        with session_factory() as db:
            row = db.query(Inbox).filter(Inbox.status.in_(('pending','retry')),
                or_(Inbox.next_attempt_at.is_(None),Inbox.next_attempt_at <= current)).order_by(Inbox.id).with_for_update(skip_locked=True).first()
            if row is None:
                return {'processed':0,'status':'idle'}
            row_id = row.id
            tenant,config = _config(row.slug,row.shop_id,row.customer_id)
            if tenant != row.tenant_id:
                fail(409,'CONNECTION_SCOPE_CHANGED','Notification connection scope changed.')
            _secret(config)  # Removed/missing verifier configuration pauses queued work.
            # Validate persisted payload again; raw digest is for replay, not source truth.
            value,_ = _parse(json.dumps(row.payload,separators=(',',':')).encode())
            if (value['event_id'],value['shop_id'],value['customer_id'],value['repair_order_id'],value['kind']) != (
                    row.event_id,row.shop_id,row.customer_id,row.repair_order_id,row.event_kind):
                fail(409,'EVENT_STORAGE_CONFLICT','Stored notification requires review.')
            f.lock_business(db,tenant)
            if not db.query(Tenant).filter_by(id=tenant,is_active=True).first():
                fail(409,'CONNECTION_SCOPE_CHANGED','Notification business is unavailable.')
            row.attempts += 1
            if sync_fn is None:
                from app.services.dieselbridge_financial import sync_financial
                sync_fn = sync_financial
            result = await sync_fn(db,tenant,row.slug,repair_order_ids=[row.repair_order_id],
                idempotency_key='wakeup:'+row.event_id,automatic=True)
            row.status = 'completed';row.completed_at=current;row.next_attempt_at=None
            row.last_error_code=None;row.result=result
            db.commit()
            return {'processed':1,'status':'completed','event_id':row.event_id}
    except Exception as exc:
        if row_id is None:
            # A database outage cannot safely be converted into a completed job.
            raise
        with session_factory() as db:
            row = db.query(Inbox).filter_by(id=row_id).with_for_update().first()
            if row is None or row.status == 'completed':
                return {'processed':0,'status':'already_completed'}
            code = _error_code(exc)
            if code in PAUSED_CODES:
                row.status = 'retry';row.last_error_code = code
                row.next_attempt_at = current+timedelta(seconds=60)
                db.commit()
                return {'processed':1,'status':'paused','event_id':row.event_id,'error_code':code}
            row.attempts += 1
            row.status = 'needs_review' if row.attempts >= MAX_ATTEMPTS else 'retry'
            row.last_error_code = code
            row.next_attempt_at = None if row.status == 'needs_review' else current+timedelta(seconds=min(3600,15*(2**min(row.attempts-1,8))))
            db.commit()
            return {'processed':1,'status':row.status,'event_id':row.event_id,'error_code':row.last_error_code}


async def financial_events_worker(session_factory, stop_event, *, poll_seconds=2.0):
    """One bounded worker loop. Explicit application lifecycle must start/stop it."""
    while not stop_event.is_set():
        try:
            result = await asyncio.to_thread(lambda:asyncio.run(process_pending_once(session_factory)))
        except Exception:
            result = {'processed':0,'status':'database_unavailable'}
        if result.get('processed'):
            continue
        try:
            await asyncio.wait_for(stop_event.wait(),timeout=max(0.1,poll_seconds))
        except asyncio.TimeoutError:
            pass
