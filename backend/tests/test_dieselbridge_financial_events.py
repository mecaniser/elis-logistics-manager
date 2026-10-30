"""Signed notifications are wake-ups, never financial truth."""
import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from app.database import get_db
from app.models.dieselbridge_events import DieselBridgeFinancialInbox
from app.models.repair import Repair
from app.models.truck import Truck
from app.routers.dieselbridge_webhooks import router
from app.services import dieselbridge_financial_events as events

NOW=datetime(2026,10,30,12,tzinfo=timezone.utc)
SHOP='828acd84-38bf-4a66-8fa1-cdf076f4e241'
CUSTOMER='1dd0a2cd-f621-47e9-b06c-14990c90e7fe'
SECRET='fixture-only-event-signing-value-32-plus'
C={'tenant_id':1,'slug':'shop','shop_id':SHOP,'bill_to_id':CUSTOMER,
   'base_url':'https://source.example','api_key_env':'FIXTURE_SOURCE_KEY','event_secret_env':'FIXTURE_EVENT_KEY'}


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS',json.dumps([C]))
    monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED','true')
    monkeypatch.setenv('FIXTURE_EVENT_KEY',SECRET)
    monkeypatch.setenv('FIXTURE_SOURCE_KEY','fixture-only-read-key')


def payload(**changes):
    return {'version':'db094-financial-wakeup-v1','event_id':str(uuid4()),'shop_id':SHOP,
        'customer_id':CUSTOMER,'repair_order_id':str(uuid4()),'kind':'invoice_finalized',
        'occurred_at':NOW.isoformat(),**changes}


def packet(value=None, sent=NOW):
    body=json.dumps(value or payload(),separators=(',',':')).encode()
    timestamp=str(int(sent.timestamp()))
    signature=hmac.new(SECRET.encode(),timestamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
    return body,{'x-dbn-event-id':json.loads(body)['event_id'],'x-dbn-timestamp':timestamp,'x-dbn-signature':'v1='+signature}


def receive(db,body,headers):
    return events.receive_event(db,'shop',body,headers,now=NOW)


def test_valid_event_is_durable_wakeup_and_duplicate_is_acknowledged(db):
    body,headers=packet();first=receive(db,body,headers);db.commit()
    assert first['status']=='queued' and first['duplicate'] is False
    second=receive(db,body,headers);db.commit()
    assert second['duplicate'] is True
    row=db.query(DieselBridgeFinancialInbox).one()
    assert row.status=='pending' and row.attempts==0
    assert row.tenant_id==1 and row.repair_order_id==json.loads(body)['repair_order_id']
    assert db.query(Repair).count()==0


@pytest.mark.parametrize('mutation',['body','signature','event_header','timestamp','scope','extra_field'])
def test_tampering_or_invalid_contract_never_creates_job(db,mutation):
    value=payload()
    if mutation=='scope':value['customer_id']=str(uuid4())
    if mutation=='extra_field':value['amount']='1000.00'
    body,headers=packet(value)
    if mutation=='body':body=body.replace(b'invoice_finalized',b'invoice_cancelled')
    if mutation=='signature':headers['x-dbn-signature']='v1='+'0'*64
    if mutation=='event_header':headers['x-dbn-event-id']=str(uuid4())
    if mutation=='timestamp':headers['x-dbn-timestamp']='invalid'
    with pytest.raises(HTTPException):receive(db,body,headers)
    assert db.query(DieselBridgeFinancialInbox).count()==0


def test_replay_conflict_and_expired_signature(db):
    value=payload();body,headers=packet(value);receive(db,body,headers);db.commit()
    changed,changed_headers=packet({**value,'kind':'invoice_cancelled'})
    with pytest.raises(HTTPException) as conflict:receive(db,changed,changed_headers)
    assert conflict.value.status_code==409
    old,old_headers=packet(payload(),sent=NOW-timedelta(seconds=301))
    with pytest.raises(HTTPException) as expired:receive(db,old,old_headers)
    assert expired.value.status_code==401
    assert db.query(DieselBridgeFinancialInbox).count()==1


@pytest.mark.parametrize('missing',['secret','flag','same_secret','same_env'])
def test_unconfigured_or_reused_secret_fails_closed(db,monkeypatch,missing):
    if missing=='secret':monkeypatch.delenv('FIXTURE_EVENT_KEY')
    elif missing=='flag':monkeypatch.delenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED')
    elif missing=='same_secret':monkeypatch.setenv('FIXTURE_SOURCE_KEY',SECRET)
    else:monkeypatch.setenv('ELIS_DIESELBRIDGE_CONNECTIONS',json.dumps([{**C,'event_secret_env':'FIXTURE_SOURCE_KEY'}]))
    body,headers=packet()
    with pytest.raises(HTTPException) as error:receive(db,body,headers)
    assert error.value.status_code==503
    assert db.query(DieselBridgeFinancialInbox).count()==0


def test_router_rejects_oversized_body_duplicate_headers_and_request_tenant(db,monkeypatch):
    app=FastAPI();app.include_router(router,prefix='/api/v1/accounting/dieselbridge')
    app.dependency_overrides[get_db]=lambda:db
    monkeypatch.setattr(events,'utcnow',lambda:NOW)
    with TestClient(app) as client:
        body,headers=packet();headers['content-type']='application/json'
        path='/api/v1/accounting/dieselbridge/webhooks/shop'
        assert client.post(path,content=body,headers=headers).status_code==202
        assert client.post(path,content=b'x'*16385,headers=headers).status_code==413
        assert client.post(path,content=body,headers={**headers,'content-length':'9'*5000}).status_code==413
        assert client.post(path,content=body,headers={**headers,'x-tenant-id':'2'}).status_code==400
        duplicate=list(headers.items())+[('x-dbn-signature',headers['x-dbn-signature'])]
        assert client.post(path,content=body,headers=duplicate).status_code==400
    assert db.query(DieselBridgeFinancialInbox).count()==1


def test_worker_refetch_is_atomic_idempotent_and_scoped(db):
    body,headers=packet();receive(db,body,headers);db.commit()
    sessions=sessionmaker(bind=db.get_bind(),autoflush=False)
    calls=[]
    async def sync(worker_db,tenant,slug,**kwargs):
        calls.append((tenant,slug,kwargs))
        truck=Truck(tenant_id=tenant,name='Fixture',vehicle_type='truck',vin='fixture')
        worker_db.add(truck);worker_db.flush()
        return {'created':1,'review_required':0,'blocked':0}
    first=asyncio.run(events.process_pending_once(sessions,sync_fn=sync,now=NOW))
    second=asyncio.run(events.process_pending_once(sessions,sync_fn=sync,now=NOW))
    assert first['status']=='completed' and second['processed']==0
    assert calls==[(1,'shop',{'repair_order_ids':[json.loads(body)['repair_order_id']],
        'idempotency_key':'wakeup:'+json.loads(body)['event_id'],'automatic':True})]
    db.expire_all();row=db.query(DieselBridgeFinancialInbox).one()
    assert row.status=='completed' and row.result['created']==1 and row.attempts==1
    assert db.query(Truck).count()==1


def test_worker_failure_rolls_back_then_durably_retries_without_private_error(db):
    body,headers=packet();receive(db,body,headers);db.commit()
    sessions=sessionmaker(bind=db.get_bind(),autoflush=False)
    async def broken(worker_db,*args,**kwargs):
        worker_db.add(Truck(tenant_id=1,name='Rollback fixture',vehicle_type='truck',vin='rollback'))
        worker_db.flush()
        raise RuntimeError('private credential or payload must never be persisted')
    failed=asyncio.run(events.process_pending_once(sessions,sync_fn=broken,now=NOW))
    assert failed['status']=='retry'
    db.expire_all();row=db.query(DieselBridgeFinancialInbox).one()
    assert row.attempts==1 and row.last_error_code=='FINANCIAL_SYNC_FAILED'
    assert row.next_attempt_at is not None and db.query(Truck).count()==0
    assert asyncio.run(events.process_pending_once(sessions,sync_fn=broken,now=NOW))['processed']==0
    async def recovered(*args,**kwargs):return {'created':0,'review_required':1,'blocked':0}
    done=asyncio.run(events.process_pending_once(sessions,sync_fn=recovered,now=NOW+timedelta(minutes=1)))
    assert done['status']=='completed'
    db.expire_all();assert db.query(DieselBridgeFinancialInbox).one().attempts==2


def test_disabled_worker_never_fetches_or_changes_pending_job(db,monkeypatch):
    body,headers=packet();receive(db,body,headers);db.commit()
    monkeypatch.delenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED')
    async def forbidden(*a,**kw):raise AssertionError('Source must not be called')
    result=asyncio.run(events.process_pending_once(sessionmaker(bind=db.get_bind()),sync_fn=forbidden,now=NOW))
    assert result=={'processed':0,'status':'disabled'}
    assert db.query(DieselBridgeFinancialInbox).one().attempts==0


def test_duplicate_still_requires_valid_fresh_signature(db):
    body,headers=packet();receive(db,body,headers);db.commit()
    with pytest.raises(HTTPException):receive(db,body,{**headers,'x-dbn-signature':'v1='+'0'*64})
    refreshed_body,refreshed=packet(json.loads(body),sent=NOW+timedelta(seconds=100))
    assert refreshed_body==body
    assert events.receive_event(db,'shop',body,refreshed,now=NOW+timedelta(seconds=100))['duplicate']


def test_duplicate_json_keys_and_non_utc_dates_rejected_before_writes(db):
    value=payload(occurred_at='2026-10-30T12:00:00+01:00')
    body,headers=packet(value)
    with pytest.raises(HTTPException) as error:receive(db,body,headers)
    assert error.value.status_code==400
    body,headers=packet()
    body=body[:-1]+b',"kind":"invoice_cancelled"}'
    with pytest.raises(HTTPException) as error:receive(db,body,headers)
    assert error.value.status_code==400
    assert db.query(DieselBridgeFinancialInbox).count()==0


def test_missing_secret_pauses_queued_work_without_consuming_retry_budget(db,monkeypatch):
    body,headers=packet();receive(db,body,headers);db.commit()
    row=db.query(DieselBridgeFinancialInbox).one();row.attempts=events.MAX_ATTEMPTS-1;db.commit()
    monkeypatch.delenv('FIXTURE_EVENT_KEY')
    async def forbidden(*args,**kwargs):raise AssertionError('Missing verifier must pause work')
    result=asyncio.run(events.process_pending_once(sessionmaker(bind=db.get_bind()),sync_fn=forbidden,now=NOW))
    assert result['status']=='paused' and result['error_code']=='WEBHOOK_NOT_CONFIGURED'
    db.expire_all();row=db.query(DieselBridgeFinancialInbox).one()
    assert row.attempts==events.MAX_ATTEMPTS-1 and row.next_attempt_at is not None
    assert asyncio.run(events.process_pending_once(sessionmaker(bind=db.get_bind()),sync_fn=forbidden,now=NOW))['processed']==0


def test_repeated_processing_failure_reaches_review_without_losing_job(db):
    body,headers=packet();receive(db,body,headers);db.commit()
    row=db.query(DieselBridgeFinancialInbox).one();row.attempts=events.MAX_ATTEMPTS-1;db.commit()
    async def broken(*args,**kwargs):raise HTTPException(502,detail={'code':'SOURCE_UNAVAILABLE','message':'private details'})
    result=asyncio.run(events.process_pending_once(sessionmaker(bind=db.get_bind()),sync_fn=broken,now=NOW))
    assert result['status']=='needs_review' and result['error_code']=='SOURCE_UNAVAILABLE'
    db.expire_all();row=db.query(DieselBridgeFinancialInbox).one()
    assert row.attempts==events.MAX_ATTEMPTS and row.next_attempt_at is None
    assert row.status=='needs_review' and row.payload['event_id']==json.loads(body)['event_id']


def test_persisted_scope_mismatch_requires_review_without_source_calls(db):
    body,headers=packet();receive(db,body,headers);db.commit()
    row=db.query(DieselBridgeFinancialInbox).one()
    row.payload={**row.payload,'customer_id':str(uuid4())};db.commit()
    async def forbidden(*args,**kwargs):raise AssertionError('Invalid stored scope must not fetch')
    result=asyncio.run(events.process_pending_once(sessionmaker(bind=db.get_bind()),sync_fn=forbidden,now=NOW))
    assert result['error_code']=='EVENT_STORAGE_CONFLICT'
