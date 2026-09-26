from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from app.auth_utils import SESSION_COOKIE_NAME, create_session_token
from app.models.bank_monitor import (BankMonitorConfig, BankProviderConnection, BankProfile, BankProfileAccount,
    BankAccountIdentity, BankProfileRoute, BankProfileDraft, BankTransferDraft, BankProfileRun)
from app.services import bank_profiles as service, plaid_bank
from app.services.bank_monitor import MonitorRules


def headers(tenant=1):
    return {'X-Tenant-ID': str(tenant), 'X-Bank-Monitor-Action': 'manage-bank-profiles'}


def row(id, mask, kind='checking', amount=1000):
    return {'account_id': id, 'mask': mask, 'type': 'depository' if kind == 'checking' else 'loan',
        'subtype': kind if kind == 'checking' else 'line of credit', 'name': f'Account {mask}',
        'balances': {'current': amount, 'available': amount, 'iso_currency_code': 'USD'}}


@pytest.fixture
def setup(client, db, monkeypatch):
    monkeypatch.setenv('APP_AUTH_USERNAME', 'profiles-test')
    monkeypatch.setenv('APP_AUTH_SECRET', 'profiles-test-secret')
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1')
    monkeypatch.setattr(plaid_bank, 'configured', lambda: True)
    monkeypatch.setattr(plaid_bank, 'environment', lambda: 'production')
    monkeypatch.setattr(plaid_bank, 'decrypt_token', lambda value: value)
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token('profiles-test'))
    now = datetime.now(timezone.utc)
    rules = MonitorRules(checking=[{'nickname': 'Business', 'last4': '3304'}], sources=[{'nickname': 'Credit', 'last4': '2829'}])
    db.add(BankMonitorConfig(tenant_id=1, enabled=True, rules=rules.model_dump(), updated_at=now))
    db.add(BankProviderConnection(tenant_id=1, provider='plaid', item_id='legacy', institution_id=plaid_bank.TRULIANT_INSTITUTION_ID,
        encrypted_access_token='legacy', account_map={'3304': {'account_id': 'old-checking', 'kind': 'checking'}, '2829': {'account_id': 'old-credit', 'kind': 'credit'}},
        status='linked', linked_at=now))
    db.commit()
    assert client.post('/api/bank-monitor/profiles/initialize', headers=headers()).status_code == 200
    legacy = db.query(BankProfile).one()
    p = BankProfile(id=str(uuid4()), tenant_id=1, name='Main Business', item_id='business',
        institution_id=plaid_bank.TRULIANT_INSTITUTION_ID, encrypted_access_token='business', status='linked', legacy=False, created_at=now)
    db.add(p); db.commit()
    monkeypatch.setattr(plaid_bank, 'item', lambda token: {'item_id': token, 'institution_id': plaid_bank.TRULIANT_INSTITUTION_ID})
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', lambda token: [row('new-checking', '3304'), row('new-credit', '8264', 'credit', 2000)] if token == 'business' else [row('old-checking', '3304'), row('old-credit', '2829', 'credit', 2000)])
    monkeypatch.setattr(plaid_bank, 'transaction_visibility', lambda token, mapping: {'pending_debit_cents': {key: 10000 if value['kind'] == 'checking' else 0 for key, value in mapping.items()}, 'pending_entries': {key: 1 for key in mapping}})
    service.sync_profile(db, p); db.commit()
    return client, p, legacy


def resolve_and_route(client, db, p):
    membership = db.query(BankProfileAccount).filter_by(profile_id=p.id, last4='3304').one()
    canonical = db.query(BankAccountIdentity).filter_by(last4='3304').one()
    response = client.post(f'/api/bank-monitor/profiles/{p.id}/accounts/{membership.id}/resolve', headers=headers(), json={'account_id': canonical.id})
    assert response.status_code == 200, response.text
    destination = db.query(BankProfileAccount).filter_by(profile_id=p.id, last4='8264').one()
    response = client.post('/api/bank-monitor/profiles/routes', headers=headers(), json={'profile_id': p.id, 'source_id': canonical.id, 'destination_id': destination.account_id, 'bank_route_confirmed': True})
    assert response.status_code == 200, response.text
    return response.json()['routes'][0]


def test_migration_preserves_old_consent_and_is_idempotent(setup, db):
    client, p, legacy = setup
    for _ in range(2):
        assert client.post('/api/bank-monitor/profiles/initialize', headers=headers()).status_code == 200
    assert db.query(BankProfile).count() == 2
    assert db.get(BankProviderConnection, 1).encrypted_access_token == 'legacy'
    assert db.query(BankAccountIdentity).filter_by(last4='3304').count() == 1
    assert db.query(BankProfileAccount).filter_by(profile_id=p.id, last4='3304').one().account_id is None


def test_overlap_requires_explicit_resolution_and_scopes_route(setup, db):
    client, p, legacy = setup
    checking = db.query(BankAccountIdentity).filter_by(last4='3304').one()
    credit = db.query(BankAccountIdentity).filter_by(last4='8264').one()
    response = client.post('/api/bank-monitor/profiles/routes', headers=headers(), json={'profile_id': p.id, 'source_id': checking.id, 'destination_id': credit.id, 'bank_route_confirmed': True})
    assert response.status_code == 409
    route = resolve_and_route(client, db, p)
    assert route['profile_id'] == p.id
    response = client.post('/api/bank-monitor/profiles/routes', headers=headers(), json={'profile_id': legacy.id, 'source_id': checking.id, 'destination_id': credit.id, 'bank_route_confirmed': True})
    assert response.status_code == 409  # 8264 is absent from the consolidated login.


def test_review_draft_preparation_and_session_binding(setup, db):
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    response = client.post(f"/api/bank-monitor/profiles/routes/{route['id']}/review", headers=headers())
    assert response.status_code == 200, response.text
    review = response.json()
    assert review['limit_cents'] == 90000
    response = client.post(f"/api/bank-monitor/profiles/reviews/{review['id']}/draft", headers=headers(), json={'amount_cents': 90001})
    assert response.status_code == 409
    response = client.post(f"/api/bank-monitor/profiles/reviews/{review['id']}/draft", headers=headers(), json={'amount_cents': 50000})
    assert response.status_code == 200, response.text
    draft = response.json()['draft']
    assert draft['bank_session']['profile_name'] == 'Main Business'
    assert draft['to_last4'] == '8264'
    assert client.post(f"/api/bank-monitor/profiles/reviews/{review['id']}/draft", headers=headers(), json={'amount_cents': 1000}).status_code == 409
    response = client.post(f"/api/bank-monitor/drafts/{draft['id']}/prepare", headers={**headers(), 'X-Bank-Monitor-Action': 'reviewed-transfer'})
    assert response.status_code == 200, response.text
    assert response.json()['bank_session']['profile_id'] == p.id


def test_shared_account_reserves_across_profiles_and_legacy_drafts(setup, db):
    client, p, legacy = setup
    route = resolve_and_route(client, db, p)
    checking = db.query(BankAccountIdentity).filter_by(last4='3304').one()
    checking.reserve_cents = 5000
    db.add(BankTransferDraft(id=str(uuid4()), tenant_id=1, charge_reference='old-draft', amount_cents=20000,
        from_last4='3304', to_last4='2829', memo='Rpy old transfer', status='prepared_awaiting_submission', created_at=datetime.now(timezone.utc)))
    db.commit()
    response = client.post(f"/api/bank-monitor/profiles/routes/{route['id']}/review", headers=headers())
    assert response.json()['limit_cents'] == 65000
    assert response.json()['reserved_draft_cents'] == 20000


def test_disabled_routes_stale_reads_and_non_usd_fail_closed(setup, db):
    client, p, _ = setup
    r = resolve_and_route(client, db, p)
    route = db.get(BankProfileRoute, r['id'])
    p.last_checked_at = datetime.now(timezone.utc) - timedelta(minutes=6)
    with pytest.raises(Exception, match='Refresh this banking profile'):
        service.transfer_limit(db, route)
    p.last_checked_at = datetime.now(timezone.utc)
    source = db.query(BankProfileAccount).filter_by(profile_id=p.id, last4='3304').one()
    source.balance = {**source.balance, 'currency': 'CAD'}
    with pytest.raises(Exception, match='US dollar'):
        service.transfer_limit(db, route)
    route.enabled = False
    with pytest.raises(Exception, match='disabled'):
        service.transfer_limit(db, route)


def test_old_global_routes_disabled_in_multi_profile_mode(setup):
    client, _, _ = setup
    response = client.post('/api/bank-monitor/transfer-reviews', headers={**headers(), 'X-Bank-Monitor-Action': 'review-bank-transfers'}, json={})
    assert response.status_code == 409
    assert 'profile' in response.json()['detail']


def test_independent_sync_failure_and_tenant_isolation(setup, db, monkeypatch):
    client, p, legacy = setup
    def read(token):
        if token == 'business': raise plaid_bank.PlaidBankError('provider_reauthorization_required')
        return [row('old-checking', '3304'), row('old-credit', '2829', 'credit')]
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', read)
    service.run_due_profiles(db, datetime(2026, 9, 26, 22, tzinfo=timezone.utc))
    assert {r.status for r in db.query(BankProfileRun)} == {'synced', 'provider_reauthorization_required'}
    service.run_due_profiles(db, datetime(2026, 9, 26, 23, tzinfo=timezone.utc))
    assert db.query(BankProfileRun).count() == 2
    assert client.post(f'/api/bank-monitor/profiles/{p.id}/sync', headers=headers(2)).status_code == 404
    assert client.post(f'/api/bank-monitor/profiles/{p.id}/sync', headers={'X-Tenant-ID': '1'}).status_code == 403


def test_reconciliation_uses_business_connection_not_legacy(setup, db, monkeypatch):
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    review = client.post(f"/api/bank-monitor/profiles/routes/{route['id']}/review", headers=headers()).json()
    draft = client.post(f"/api/bank-monitor/profiles/reviews/{review['id']}/draft", headers=headers(), json={'amount_cents': 1000}).json()['draft']
    db.get(BankTransferDraft, draft['id']).status = 'prepared_awaiting_submission'; db.commit()
    seen = []
    def match(token, mapping, **kwargs):
        seen.append((token, mapping))
        return {'status': 'not_found'}
    monkeypatch.setattr(plaid_bank, 'transfer_match', match)
    response = client.post(f"/api/bank-monitor/drafts/{draft['id']}/plaid-match", headers={**headers(), 'X-Bank-Monitor-Action': 'verify-plaid-transfer'}, json={'automatic': True})
    assert response.status_code == 200, response.text
    assert seen[0][0] == 'business'
    assert seen[0][1]['8264']['account_id'] == 'new-credit'


def test_second_institution_link_preserves_first_connection_and_hides_tokens(setup, db, monkeypatch):
    client, _, _ = setup
    monkeypatch.setattr(plaid_bank, 'link_token', lambda *args, **kwargs: 'new-link-token')
    monkeypatch.setattr(plaid_bank, 'exchange', lambda token: ('new-secret-token', 'second-bank-item'))
    monkeypatch.setattr(plaid_bank, 'encrypt_token', lambda token: f'encrypted:{token}')
    monkeypatch.setattr(plaid_bank, 'item', lambda token: {'item_id': 'second-bank-item', 'institution_id': 'another-institution'})
    monkeypatch.setattr(service, 'sync_profile', lambda db, profile: None)
    first = client.post('/api/bank-monitor/profiles/link', headers=headers(), json={'name': 'Other bank'}).json()
    payload = {'attempt_id': first['attempt_id'], 'link_token': first['link_token'], 'public_token': 'public-test'}
    response = client.post('/api/bank-monitor/profiles/exchange', headers=headers(), json=payload)
    assert response.status_code == 200, response.text
    assert len(response.json()['profiles']) == 3
    assert 'secret-token' not in response.text and 'encrypted_access_token' not in response.text
    assert db.get(BankProviderConnection, 1).item_id == 'legacy'
    assert client.post('/api/bank-monitor/profiles/exchange', headers=headers(), json=payload).status_code == 409


def test_other_authorized_tenant_cannot_use_profile(setup, db, monkeypatch):
    from app.models.tenant import Tenant
    client, p, _ = setup
    monkeypatch.setenv('BANK_MONITOR_TENANT_IDS', '1,2')
    db.add(Tenant(id=2, name='Other business', business_type='logistics', is_active=True))
    db.add(BankMonitorConfig(tenant_id=2, enabled=False, rules=MonitorRules().model_dump(), updated_at=datetime.now(timezone.utc)))
    db.commit()
    assert client.post(f'/api/bank-monitor/profiles/{p.id}/sync', headers=headers(2)).status_code == 404
    assert client.get('/api/bank-monitor/profiles', headers=headers(2)).json()['profiles'] == []


def test_lower_balance_blocks_claim_without_losing_draft(setup, db, monkeypatch):
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    review = client.post(f"/api/bank-monitor/profiles/routes/{route['id']}/review", headers=headers()).json()
    draft = client.post(f"/api/bank-monitor/profiles/reviews/{review['id']}/draft", headers=headers(), json={'amount_cents': 90000}).json()['draft']
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', lambda token: [row('new-checking', '3304', amount=300), row('new-credit', '8264', 'credit', 2000)])
    response = client.post(f"/api/bank-monitor/drafts/{draft['id']}/prepare", headers={**headers(), 'X-Bank-Monitor-Action': 'reviewed-transfer'})
    assert response.status_code == 409
    assert db.get(BankTransferDraft, draft['id']).status == 'reviewed'


def test_credit_line_advance_and_checking_transfer_are_explicit(setup, db):
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    response = client.post('/api/bank-monitor/profiles/routes', headers=headers(), json={'profile_id': p.id, 'source_id': route['destination_id'], 'destination_id': route['source_id'], 'bank_route_confirmed': True})
    assert response.status_code == 200, response.text
    advance = next(r for r in response.json()['routes'] if r['source_id'] == route['destination_id'])
    review = client.post(f"/api/bank-monitor/profiles/routes/{advance['id']}/review", headers=headers())
    assert review.status_code == 200 and review.json()['kind'] == 'coverage'
    # A credit card cannot silently become an advance source.
    member = db.query(BankProfileAccount).filter_by(profile_id=p.id, account_id=route['destination_id']).one()
    member.subtype = 'credit card'; db.commit()
    with pytest.raises(Exception, match='credit line'):
        service.transfer_limit(db, db.get(BankProfileRoute, advance['id']))
