import asyncio
import os
from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from app.database import get_db
from app.routers import dieselbridge_webhooks as route
from app.services import dieselbridge_signal as signal
from tests.test_dieselbridge_financial_events import configured,packet,NOW


@pytest.mark.parametrize('outcome',['success','invalid','commit_failure'])
def test_wake_occurs_after_successful_durable_commit_only(db,monkeypatch,outcome):
    app=FastAPI();app.include_router(route.router)
    app.dependency_overrides[get_db]=lambda:db
    from app.services import dieselbridge_financial_events as events
    monkeypatch.setattr(events,'utcnow',lambda:NOW)
    order=[]
    app.state.dbn_financial_worker_wake=SimpleNamespace(set=lambda:order.append('wake'))
    original=db.commit
    def commit():
        order.append('commit')
        if outcome=='commit_failure':raise RuntimeError('fixture failure')
        original()
    monkeypatch.setattr(db,'commit',commit)
    body,headers=packet();headers['content-type']='application/json'
    if outcome=='invalid':headers['x-dbn-signature']='v1'+'0'*64
    with TestClient(app,raise_server_exceptions=False) as client:
        response=client.post('/webhooks/shop',content=body,headers=headers)
    assert response.status_code=={'success':202,'invalid':401,'commit_failure':500}[outcome]
    assert order=={'success':['commit','wake'],'invalid':[],'commit_failure':['commit']}[outcome]


def test_listener_reconnection_drains_durable_inbox_before_socket_wait(monkeypatch):
    stop=asyncio.Event();wake=asyncio.Event();calls=[]
    class Connection:
        def close(self):calls.append('close')
    monkeypatch.setattr(signal,'_connect',lambda engine:Connection())
    def receive(connection):
        assert wake.is_set()
        calls.append('receive');stop.set();return True
    monkeypatch.setattr(signal,'_receive',receive)
    asyncio.run(signal.listen(SimpleNamespace(dialect=SimpleNamespace(name='postgresql')),stop,wake))
    assert calls==['receive','close']


# Real PostgreSQL verifies delivery is cross-connection and commit-bound.
@pytest.mark.skipif(not os.getenv("DB094_POSTGRES_TEST_URL"), reason="Disposable PostgreSQL test database not configured")
def test_postgres_notification_has_no_payload_and_is_transactional(postgres):
    engine,sessions,tenant=postgres
    connection=signal._connect(engine)
    try:
        with sessions() as db:
            signal.notify(db);db.rollback()
            assert not signal._receive(connection)
            signal.notify(db);db.commit()
            assert signal._receive(connection)
    finally:connection.close()


from tests.test_dieselbridge_postgres import postgres
