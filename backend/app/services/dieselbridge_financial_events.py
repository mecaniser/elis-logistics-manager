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
import logging
import os
import re
from uuid import UUID,uuid4
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


def _utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


async def process_pending_once(session_factory, *, sync_fn=None, now=None):
    """Lease briefly, fetch outside locks, then atomically apply and acknowledge."""
    if not enabled():return {'processed':0,'status':'disabled'}
    current=now or utcnow();claim=None;row_id=None
    try:
        with session_factory() as db:
            due=or_(Inbox.next_attempt_at.is_(None),Inbox.next_attempt_at<=current)
            row=db.query(Inbox).filter(Inbox.status.in_(('pending','retry','processing')),due).order_by(Inbox.id).with_for_update(skip_locked=True).first()
            if row is None:return {'processed':0,'status':'idle'}
            row_id=row.id
            tenant,config=_config(row.slug,row.shop_id,row.customer_id)
            if tenant!=row.tenant_id:fail(409,'CONNECTION_SCOPE_CHANGED','Notification business changed.')
            _secret(config)
            value,_=_parse(json.dumps(row.payload,separators=(',',':')).encode())
            if (value['event_id'],value['shop_id'],value['customer_id'],value['repair_order_id'],value['kind'])!=(row.event_id,row.shop_id,row.customer_id,row.repair_order_id,row.event_kind):
                fail(409,'EVENT_STORAGE_CONFLICT','Stored notification requires review.')
            if not db.query(Tenant).filter_by(id=tenant,is_active=True).first():fail(409,'CONNECTION_SCOPE_CHANGED','Notification business unavailable.')
            row.attempts+=1;row.status='processing';row.next_attempt_at=current+timedelta(minutes=2)
            claim={'id':row.id,'tenant':tenant,'slug':row.slug,'event_id':row.event_id,'repair_order_id':row.repair_order_id,'attempt':row.attempts,'lease':row.next_attempt_at}
            db.commit()
        source=None
        if sync_fn is None:
            from app.services.dieselbridge_financial import manifest,sync_financial
            source=await manifest(config);sync_fn=sync_financial
        with session_factory() as db:
            f.lock_business(db,tenant)
            row=db.query(Inbox).filter_by(id=claim['id']).with_for_update().first()
            if not row or row.status!='processing' or row.attempts!=claim['attempt'] or _utc(row.next_attempt_at)!=_utc(claim['lease']):
                return {'processed':0,'status':'stale_lease'}
            kwargs={'repair_order_ids':[claim['repair_order_id']],'idempotency_key':'wakeup:'+claim['event_id'],'automatic':True}
            if source is not None:kwargs['_source_manifest']=source
            result=await sync_fn(db,tenant,claim['slug'],**kwargs)
            row.status='completed';row.completed_at=current;row.next_attempt_at=None;row.last_error_code=None;row.result=result
            db.commit()
            return {'processed':1,'status':'completed','event_id':claim['event_id']}
    except Exception as exc:
        code=_error_code(exc)
        with session_factory() as db:
            if claim:
                row=db.query(Inbox).filter_by(id=claim['id']).with_for_update().first()
                if not row or row.status!='processing' or row.attempts!=claim['attempt'] or _utc(row.next_attempt_at)!=_utc(claim['lease']):
                    return {'processed':0,'status':'stale_lease'}
            elif row_id is not None:
                row=db.query(Inbox).filter_by(id=row_id).with_for_update().first()
                # Validation failed before claiming. Another worker may have
                # reclaimed the row after rollback; never overwrite its lease.
                if (not row or row.status not in ('pending','retry','processing')
                        or (row.next_attempt_at is not None and _utc(row.next_attempt_at)>_utc(current))):
                    return {'processed':0,'status':'stale_lease'}
            else:raise
            if row.status=='completed':return {'processed':0,'status':'already_completed'}
            if code in PAUSED_CODES:
                if claim:row.attempts-=1
                row.status='retry';row.next_attempt_at=current+timedelta(seconds=60)
                outcome='paused'
            else:
                if not claim:row.attempts+=1
                row.status='needs_review' if row.attempts>=MAX_ATTEMPTS else 'retry'
                row.next_attempt_at=None if row.status=='needs_review' else current+timedelta(seconds=min(3600,15*(2**min(row.attempts-1,8))))
                outcome=row.status
            row.last_error_code=code;db.commit()
            return {'processed':1,'status':outcome,'event_id':row.event_id,'error_code':code}


CATCHUP_SECONDS = 3600


async def reconcile_connections_once(session_factory, *, sync_fn=None, now=None, run_key=None):
    """Full authenticated refetch repairs missed wakeups, including before setup.

    The existing tenant lock and per-bucket operation key serialize replicas and
    restarts. Each connection commits independently; failure never acknowledges
    another connection or fabricates a payment. No webhook secret is needed for
    an authenticated pull through the already scoped source read key.
    """
    if not enabled() or os.getenv('ELIS_DIESELBRIDGE_FINANCIAL_WORKER_ENABLED','').lower() not in {'1','true'}:
        return {'status':'disabled','connections':[]}
    current = now or utcnow()
    try:
        entries = json.loads(os.getenv('ELIS_DIESELBRIDGE_CONNECTIONS','[]'))
        if not isinstance(entries,list) or len(entries)>100:raise ValueError()
        scopes = []
        for entry in entries:
            tenant,slug = entry['tenant_id'],entry['slug']
            if type(tenant) is not int or tenant <= 0 or not isinstance(slug,str):raise ValueError()
            if (tenant,slug) in scopes:raise ValueError()
            scopes.append((tenant,slug))
    except (ValueError,TypeError,KeyError):
        return {'status':'configuration_error','connections':[]}
    if sync_fn is None:
        from app.services.dieselbridge_financial import sync_financial
        sync_fn = sync_financial
    bucket = int(current.timestamp()) // CATCHUP_SECONDS
    results = []
    for tenant,slug in scopes:
        try:
            with session_factory() as db:
                d.config(tenant,slug)
                if not db.query(Tenant).filter_by(id=tenant,is_active=True).first():
                    fail(409,'CONNECTION_SCOPE_CHANGED','Notification business is unavailable.')
                # sync_financial verifies stored connection scope, fetches the
                # complete validated manifest and holds changes for source review.
                result = await sync_fn(db,tenant,slug,idempotency_key=run_key or 'catchup:v2:'+str(bucket),automatic=True)
                db.commit()
                results.append({'tenant_id':tenant,'slug':slug,'status':'completed','result':result})
        except Exception as exc:
            results.append({'tenant_id':tenant,'slug':slug,'status':'retry','error_code':_error_code(exc)})
    return {'status':'completed','connections':results}


def next_inbox_due(session_factory, *, now=None):
    current=now or utcnow()
    with session_factory() as db:
        row=db.query(Inbox.next_attempt_at).filter(Inbox.status.in_(('pending','retry','processing'))).order_by(Inbox.next_attempt_at.asc().nullsfirst()).first()
        return (_utc(row[0]) if row[0] else current) if row else None


async def _wait_for_work(stop,wake,timeout):
    tasks=[asyncio.create_task(stop.wait()),asyncio.create_task(wake.wait())]
    try:await asyncio.wait(tasks,timeout=timeout,return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            if not task.done():task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)


async def financial_events_worker(session_factory, stop_event, *, wake_event=None):
    """Push wakes promptly 24/7; durable retries and shop-hour backup set timers."""
    from app.services.dieselbridge_schedule import load_schedule
    schedule=load_schedule();wake=wake_event or asyncio.Event();startup=True
    next_backup=schedule.next_after(utcnow());drain=True;retry_due=None
    while not stop_event.is_set():
        current=utcnow()
        if startup or current>=next_backup:
            slot=schedule.due_slot(current)
            if startup or slot is not None:
                key='startup:v2:'+str(uuid4()) if startup else schedule.key(slot)
                try:
                    checked=await asyncio.to_thread(lambda:asyncio.run(reconcile_connections_once(session_factory,now=current,run_key=key)))
                except Exception:
                    checked={'status':'unavailable','connections':[]}
                    logging.getLogger(__name__).warning('DBN backup unavailable; scheduled recovery retained.')
                if checked['status']=='configuration_error':logging.getLogger(__name__).warning('DBN catch-up configuration requires review.')
                for connection in checked.get('connections',[]):
                    if connection['status']=='retry':logging.getLogger(__name__).warning('DBN catch-up paused: code=%s',connection['error_code'])
            startup=False;next_backup=schedule.next_after(utcnow());drain=True
        if wake.is_set():wake.clear();drain=True
        if retry_due is not None and current>=retry_due:drain=True
        if drain:
            try:
                result=await asyncio.to_thread(lambda:asyncio.run(process_pending_once(session_factory)))
                if result.get('processed'):continue
                retry_due=await asyncio.to_thread(lambda:next_inbox_due(session_factory,now=utcnow()))
            except Exception:
                logging.getLogger(__name__).warning('DBN inbox unavailable; retry scheduled.')
                retry_due=utcnow()+timedelta(minutes=1)
            drain=False
        deadline=min(next_backup,retry_due) if retry_due else next_backup
        await _wait_for_work(stop_event,wake,max(.1,(deadline-utcnow()).total_seconds()))
