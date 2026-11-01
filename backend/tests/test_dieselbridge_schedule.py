from datetime import datetime,timezone
import pytest
from app.services.dieselbridge_schedule import ShopSchedule,load_schedule


def utc(value):return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def test_matthews_schedule_has_hourly_opening_and_closing_checks_only():
    s=ShopSchedule()
    assert len(s.slots(utc('2026-11-01T00:00:00').date()))==11
    assert s.next_after(utc('2026-11-01T12:00:00'))==utc('2026-11-01T14:00:00')
    assert s.next_after(utc('2026-11-01T14:00:00'))==utc('2026-11-01T15:00:00')
    assert s.due_slot(utc('2026-11-01T14:20:00'))==utc('2026-11-01T14:00:00')
    assert s.due_slot(utc('2026-11-02T00:00:15'))==utc('2026-11-02T00:00:00')  # 7 p.m. closing check
    assert s.due_slot(utc('2026-11-02T00:01:00')) is None
    assert s.next_after(utc('2026-11-02T00:01:00'))==utc('2026-11-02T14:00:00')


def test_dst_weekends_and_closures_preserve_local_opening_recovery():
    s=ShopSchedule()
    assert s.next_after(utc('2026-03-08T00:30:00'))==utc('2026-03-08T13:00:00')  # spring 9 EDT
    assert s.next_after(utc('2026-11-01T00:30:00'))==utc('2026-11-01T14:00:00')  # fall 9 EST
    weekday=ShopSchedule(weekdays=(0,1,2,3,4),closed_dates=('2026-11-02',))
    assert weekday.next_after(utc('2026-10-30T23:30:00'))==utc('2026-11-03T14:00:00')
    assert weekday.due_slot(utc('2026-11-01T17:00:00')) is None
    assert weekday.due_slot(utc('2026-11-02T17:00:00')) is None
    assert weekday.key(utc('2026-11-03T14:00:00'))==weekday.key(utc('2026-11-03T14:00:00'))
    assert weekday.key(utc('2026-11-03T14:00:00'))!=s.key(utc('2026-11-03T14:00:00'))


@pytest.mark.parametrize('value',['{"weekdays":[]}','{"weekdays":[true]}','{"open_hour":19,"close_hour":9}','{"interval_hours":0}','{"timezone":"Invalid/Zone"}','{"closed_dates":["not-a-date"]}','{"unexpected":1}'])
def test_invalid_schedule_rejected_without_silent_default(monkeypatch,value):
    monkeypatch.setenv('ELIS_DIESELBRIDGE_BACKUP_SCHEDULE',value)
    with pytest.raises(ValueError,match='Invalid DBN backup schedule'):load_schedule()


def test_idle_worker_uses_timer_instead_of_two_second_database_polling(monkeypatch):
    import asyncio
    from app.services import dieselbridge_financial_events as e
    now=utc('2026-11-01T14:15:00');calls=[];stop=asyncio.Event()
    monkeypatch.setattr(e,'utcnow',lambda:now)
    async def catchup(*a,**kw):calls.append('startup');return {'status':'completed','connections':[]}
    async def pending(*a,**kw):calls.append('inbox');return {'processed':0,'status':'idle'}
    def due(*a,**kw):calls.append('deadline');return None
    async def wait(stop,wake,timeout):
        calls.append(timeout);stop.set()
    monkeypatch.setattr(e,'reconcile_connections_once',catchup);monkeypatch.setattr(e,'process_pending_once',pending)
    monkeypatch.setattr(e,'next_inbox_due',due);monkeypatch.setattr(e,'_wait_for_work',wait)
    asyncio.run(e.financial_events_worker(None,stop))
    assert calls==['startup','inbox','deadline',2700.0]


def test_outside_hours_notification_wakes_immediately_without_extra_backup(monkeypatch):
    import asyncio
    from app.services import dieselbridge_financial_events as e
    now=[utc('2026-11-02T03:00:00')];stop=asyncio.Event();wake=asyncio.Event();calls=[];waits=[]
    monkeypatch.setattr(e,'utcnow',lambda:now[0])
    async def catchup(*a,**kw):calls.append('startup');return {'status':'completed','connections':[]}
    async def pending(*a,**kw):
        calls.append('inbox')
        return {'processed':1 if calls.count('inbox')==2 else 0,'status':'completed'}
    async def wait(stop,event,timeout):
        waits.append(timeout)
        if len(waits)==1:now[0]+=e.timedelta(seconds=1);event.set()
        else:stop.set()
    monkeypatch.setattr(e,'reconcile_connections_once',catchup);monkeypatch.setattr(e,'process_pending_once',pending)
    monkeypatch.setattr(e,'next_inbox_due',lambda *a,**kw:None);monkeypatch.setattr(e,'_wait_for_work',wait)
    asyncio.run(e.financial_events_worker(None,stop,wake_event=wake))
    assert calls==['startup','inbox','inbox','inbox']
    assert waits[0]==39600.0  # no 2-second poll; next backup is 9 a.m. EST


def test_opening_catchup_recovers_after_weekend_and_closure(monkeypatch):
    import asyncio
    from app.services import dieselbridge_financial_events as e
    schedule=ShopSchedule(weekdays=(0,1,2,3,4),closed_dates=('2026-11-02',))
    now=[utc('2026-10-31T02:00:00')];stop=asyncio.Event();keys=[]
    monkeypatch.setattr(e,'utcnow',lambda:now[0])
    monkeypatch.setattr('app.services.dieselbridge_schedule.load_schedule',lambda:schedule)
    async def catchup(*a,**kw):keys.append(kw['run_key']);return {'status':'completed','connections':[]}
    async def pending(*a,**kw):return {'processed':0,'status':'idle'}
    async def wait(stop,wake,timeout):
        if len(keys)==1:
            assert timeout==(utc('2026-11-03T14:00:00')-now[0]).total_seconds()
            now[0]=utc('2026-11-03T14:00:00')
        else:stop.set()
    monkeypatch.setattr(e,'reconcile_connections_once',catchup);monkeypatch.setattr(e,'process_pending_once',pending)
    monkeypatch.setattr(e,'next_inbox_due',lambda *a,**kw:None);monkeypatch.setattr(e,'_wait_for_work',wait)
    asyncio.run(e.financial_events_worker(None,stop))
    assert keys[0].startswith('startup:v2:')
    assert keys[1]==schedule.key(utc('2026-11-03T14:00:00'))


def test_persisted_retry_deadline_wakes_worker_outside_shop_hours(monkeypatch):
    import asyncio
    from app.services import dieselbridge_financial_events as e
    now=[utc('2026-11-02T03:00:00')];stop=asyncio.Event();waits=[];calls=[]
    monkeypatch.setattr(e,'utcnow',lambda:now[0])
    async def catchup(*a,**kw):return {'status':'completed','connections':[]}
    async def pending(*a,**kw):
        calls.append(now[0]);return {'processed':0,'status':'idle'}
    async def wait(stop,wake,timeout):
        waits.append(timeout)
        if len(waits)==1:now[0]+=e.timedelta(seconds=15)
        else:stop.set()
    monkeypatch.setattr(e,'reconcile_connections_once',catchup);monkeypatch.setattr(e,'process_pending_once',pending)
    monkeypatch.setattr(e,'next_inbox_due',lambda *a,**kw:utc('2026-11-02T03:00:15') if len(calls)==1 else None)
    monkeypatch.setattr(e,'_wait_for_work',wait)
    asyncio.run(e.financial_events_worker(None,stop))
    assert waits[0]==15 and len(calls)==2
