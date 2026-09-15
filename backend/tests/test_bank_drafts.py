import pytest
from app.auth_utils import SESSION_COOKIE_NAME, create_session_token


@pytest.fixture
def session(client, monkeypatch):
    monkeypatch.setenv('APP_AUTH_USERNAME', 'bank-test')
    monkeypatch.setenv('APP_AUTH_SECRET', 'test-secret')
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('bank-test'))
    result = client.put('/api/bank-monitor', headers={'X-Tenant-ID':'1','X-Bank-Monitor-Action':'save-settings'}, json={
        'checking':[{'nickname':'Test checking','last4':'1111'}],
        'sources':[{'nickname':'Test credit','last4':'2222'}]})
    assert result.status_code == 200
    return client


H = {'X-Tenant-ID':'1','X-Bank-Monitor-Action':'reviewed-transfer'}
D = {'charge_reference':'synthetic-2026-09-14-utility', 'from_last4':'2222','to_last4':'1111',
     'amount_cents':11820,'memo':'Cvr Synthetic utility 0914'}


def test_duplicate_and_double_click_blocked(session):
    first = session.post('/api/bank-monitor/drafts', headers=H, json=D)
    assert first.status_code == 200
    assert session.post('/api/bank-monitor/drafts', headers=H, json=D).status_code == 409
    route = '/api/bank-monitor/drafts/' + first.json()['id']
    assert session.post(route+'/prepare', headers=H).status_code == 200
    assert session.post(route+'/prepare', headers=H).status_code == 409
    assert session.post(route+'/outcome', headers=H, json={'status':'completed'}).status_code == 422
    assert session.post(route+'/outcome', headers=H, json={'status':'prepared_awaiting_submission'}).status_code == 200
    assert session.post(route+'/prepare', headers=H).status_code == 409


def test_bank_status_and_effective_date_are_saved_and_refreshed(session):
    created = session.post('/api/bank-monitor/drafts', headers=H, json={
        **D, 'bank_state':'pending', 'bank_effective_date':'2026-09-15'}).json()
    assert created['bank_state'] == 'pending'
    assert created['bank_effective_date'] == '2026-09-15'
    path = '/api/bank-monitor/drafts/' + created['id'] + '/bank-details'
    updated = session.put(path, headers=H, json={'bank_state':'posted','bank_effective_date':'2026-09-16'})
    assert updated.status_code == 200
    refreshed = session.get('/api/bank-monitor/drafts', headers=H).json()[0]
    assert refreshed['bank_state'] == 'posted'
    assert refreshed['bank_effective_date'] == '2026-09-16'


def test_tenant_auth_and_write_headers(session):
    assert session.post('/api/bank-monitor/drafts',headers={'X-Tenant-ID':'1'},json=D).status_code == 403
    assert session.get('/api/bank-monitor/drafts',headers={'X-Tenant-ID':'2'}).status_code == 404
    session.cookies.clear()
    assert session.get('/api/bank-monitor/drafts',headers=H).status_code == 401


@pytest.mark.parametrize('change', [{'amount_cents':0},{'amount_cents':1.2},{'memo':'No prefix'},
                                  {'from_last4':'9999'},{'to_last4':'2222'},{'memo':'Cvr '+('x'*31)}])
def test_invalid_drafts_blocked(session, change):
    assert session.post('/api/bank-monitor/drafts',headers=H,json={**D,**change}).status_code == 422


def test_both_history_entries_required_and_cannot_be_reused(session):
    first=session.post('/api/bank-monitor/drafts',headers=H,json=D).json()
    path='/api/bank-monitor/drafts/'+first['id']
    evidence={'source':'a'*64,'destination':'b'*64}
    assert session.post(path+'/history-match',headers=H,json=evidence).status_code == 409
    session.post(path+'/prepare',headers=H)
    assert session.post(path+'/history-match',headers=H,json={'source':'a'*64,'destination':'a'*64}).status_code == 422
    assert session.post(path+'/history-match',headers=H,json=evidence).status_code == 200
    second=session.post('/api/bank-monitor/drafts',headers=H,json={**D,'charge_reference':'different-ref'}).json()
    path2='/api/bank-monitor/drafts/'+second['id']
    session.post(path2+'/prepare',headers=H)
    assert session.post(path2+'/history-match',headers=H,json=evidence).status_code == 409


def test_only_explicit_not_started_outcome_releases_requested_draft(session):
    draft = session.post('/api/bank-monitor/drafts', headers=H, json=D).json()
    path = '/api/bank-monitor/drafts/' + draft['id']
    assert session.post(path+'/prepare', headers=H).status_code == 200
    result = session.post(path+'/outcome', headers=H, json={'status':'preparation_not_started'})
    assert result.status_code == 200
    assert result.json()['status'] == 'reviewed'
    assert session.post(path+'/prepare', headers=H).status_code == 200
    assert session.post(path+'/outcome', headers=H, json={'status':'preparation_failed'}).status_code == 200
    assert session.post(path+'/outcome', headers=H, json={'status':'preparation_not_started'}).status_code == 409
    assert session.post(path+'/prepare', headers=H).status_code == 409
    retry = session.post(path+'/retry', headers=H, json={'reason':'signed_out_before_form'})
    assert retry.status_code == 200
    assert retry.json() == {'status':'reviewed','reason':'signed_out_before_form','transfers_executed':False}
    assert session.post(path+'/prepare', headers=H).status_code == 200
