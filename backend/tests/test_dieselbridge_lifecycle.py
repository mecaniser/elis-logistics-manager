"""The public HMAC URL is narrow and its financial worker is separately opt-in."""
import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import main


@pytest.mark.parametrize('financial,worker,expected',[
    ('','',False),('true','',False),('','true',False),('true','true',True),
    ('1','1',True),('yes','true',False),('true','yes',False),
])
def test_worker_requires_both_flags_and_shutdown_awaits_it(monkeypatch,financial,worker,expected):
    monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_ENABLED',financial)
    monkeypatch.setenv('ELIS_DIESELBRIDGE_FINANCIAL_WORKER_ENABLED',worker)
    events=[]
    async def fake(session_factory,stop_event,**kwargs):
        events.append('started')
        await stop_event.wait()
        events.append('stopped')
    monkeypatch.setattr(main,'financial_events_worker',fake)
    async def scenario():
        await main.start_dieselbridge_financial_worker()
        await asyncio.sleep(0)
        assert events==(['started'] if expected else [])
        first=getattr(main.app.state,'dbn_financial_worker_task',None)
        await main.start_dieselbridge_financial_worker()
        assert getattr(main.app.state,'dbn_financial_worker_task',None) is first
        await main.stop_dieselbridge_financial_worker()
        assert events==(['started','stopped'] if expected else [])
        assert main.app.state.dbn_financial_worker_task is None
    asyncio.run(scenario())


@pytest.mark.parametrize('method,path,expected',[
    ('POST','/api/v1/accounting/dieselbridge/webhooks/truck-pit-stop',200),
    ('POST','/api/v1/accounting/dieselbridge/webhooks/a_1',200),
    ('GET','/api/v1/accounting/dieselbridge/webhooks/truck-pit-stop',401),
    ('POST','/api/v1/accounting/dieselbridge/webhooks/truck-pit-stop/extra',401),
    ('POST','/api/v1/accounting/dieselbridge/webhooks/',401),
    ('POST','/api/v1/accounting/dieselbridge/webhooks/'+'a'*61,401),
    ('POST','/api/v1/accounting/dieselbridge/connections/fixture/financial-import/sync',401),
])
def test_session_exemption_is_exact_post_only(monkeypatch,method,path,expected):
    probe=FastAPI()
    @probe.api_route('/api/{path:path}',methods=['GET','POST'])
    def route(path): return {'reached':True}
    probe.add_middleware(main.SessionAuthMiddleware)
    monkeypatch.setattr(main,'APP_AUTH_USERNAME','fixture-owner')
    with TestClient(probe) as client:
        assert client.request(method,path).status_code==expected


def test_hmac_route_and_model_are_registered_before_metadata_creation():
    assert 'dieselbridge_financial_inbox' in main.Base.metadata.tables
    assert any(r.path=='/api/v1/accounting/dieselbridge/webhooks/{slug}' and 'POST' in r.methods for r in main.app.routes)
