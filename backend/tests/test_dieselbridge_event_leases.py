import asyncio
from datetime import timedelta
from sqlalchemy.orm import sessionmaker
from app.models.dieselbridge_events import DieselBridgeFinancialInbox as Inbox
from app.services import dieselbridge_financial_events as events
from tests.test_dieselbridge_financial_events import configured,packet,receive,NOW


def test_expired_job_is_recovered_and_old_lease_cannot_acknowledge_it(db):
    body,headers=packet();receive(db,body,headers);db.commit()
    row=db.query(Inbox).one();row.status='processing';row.attempts=1;row.next_attempt_at=NOW-timedelta(seconds=1);db.commit()
    sessions=sessionmaker(bind=db.get_bind(),autoflush=False)
    async def sync(*args,**kwargs):return {'created':0,'unchanged':1,'review_required':0,'blocked':0}
    result=asyncio.run(events.process_pending_once(sessions,sync_fn=sync,now=NOW))
    db.expire_all();row=db.query(Inbox).one()
    assert result['status']=='completed' and row.attempts==2


def test_event_source_fetch_holds_no_tenant_finance_lock(db,monkeypatch):
    from app.services import dieselbridge_financial as financial
    body,headers=packet();receive(db,body,headers);db.commit()
    sessions=sessionmaker(bind=db.get_bind(),autoflush=False);calls=[]
    original=events.f.lock_business
    def lock(*args,**kwargs):calls.append('lock');return original(*args,**kwargs)
    async def fetch(config):
        assert not calls
        calls.append('fetch')
        return {'fixture':'source'}
    async def apply(db,tenant,slug,**kwargs):
        assert calls==['fetch','lock']
        assert kwargs['_source_manifest']=={'fixture':'source'}
        return {'created':0,'unchanged':1,'review_required':0,'blocked':0}
    monkeypatch.setattr(events.f,'lock_business',lock)
    monkeypatch.setattr(financial,'manifest',fetch);monkeypatch.setattr(financial,'sync_financial',apply)
    assert asyncio.run(events.process_pending_once(sessions,now=NOW))['status']=='completed'


def test_reclaimed_lease_fences_old_worker_after_remote_fetch(db,monkeypatch):
    from app.services import dieselbridge_financial as financial
    body,headers=packet();receive(db,body,headers);db.commit()
    sessions=sessionmaker(bind=db.get_bind(),autoflush=False)
    async def fetch(config):
        with sessions() as other:
            row=other.query(Inbox).one();row.attempts+=1;row.next_attempt_at=NOW+timedelta(minutes=3);other.commit()
        return {}
    async def forbidden(*a,**kw):raise AssertionError('Old lease must not apply financial changes')
    monkeypatch.setattr(financial,'manifest',fetch);monkeypatch.setattr(financial,'sync_financial',forbidden)
    assert asyncio.run(events.process_pending_once(sessions,now=NOW))['status']=='stale_lease'
    db.expire_all();assert db.query(Inbox).one().status=='processing'
