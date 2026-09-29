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


def test_account_view_and_review_reopen_existing_transfer(setup, db):
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    url = f"/api/bank-monitor/profiles/routes/{route['id']}/review"
    first = client.post(url, headers=headers()).json()
    second = client.post(url, headers=headers()).json()
    created = client.post(f"/api/bank-monitor/profiles/reviews/{first['id']}/draft", headers=headers(), json={'amount_cents': 50000}).json()['draft']
    existing = client.post(url, headers=headers()).json()['existing_draft']
    assert existing['id'] == created['id']
    # A second tab with an earlier review cannot create a duplicate.
    response = client.post(f"/api/bank-monitor/profiles/reviews/{second['id']}/draft", headers=headers(), json={'amount_cents': 1000})
    assert response.status_code == 409
    assert 'already in progress' in response.json()['detail']
    dashboard = client.get('/api/bank-monitor/profiles', headers=headers()).json()
    assert dashboard['drafts'][0]['id'] == created['id']
    assert dashboard['drafts'][0]['source_id'] == route['source_id']


def test_full_payoff_requires_verified_quote_not_reported_balance(setup, db):
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    review = client.post(f"/api/bank-monitor/profiles/routes/{route['id']}/review", headers=headers()).json()
    response = client.post(f"/api/bank-monitor/profiles/reviews/{review['id']}/draft", headers=headers(), json={'amount_cents': 50000, 'intent': 'full_payoff'})
    assert response.status_code == 409
    assert 'payoff quote' in response.json()['detail']
    assert db.query(BankTransferDraft).count() == 0
    assert client.post(f"/api/bank-monitor/profiles/reviews/{review['id']}/draft", headers=headers(), json={'amount_cents': 50000, 'intent': 'payment'}).status_code == 200


def test_preferences_route_scope_and_migration_review(setup, db):
    client, p, legacy = setup
    route = resolve_and_route(client, db, p)
    payload = {'monitor': True, 'repayment': True, 'funding_order': [], 'repayment_order': [route['id']]}
    url = f'/api/bank-monitor/profiles/{p.id}/preferences'
    assert client.put(url, headers=headers(2), json=payload).status_code == 404
    assert client.put(f'/api/bank-monitor/profiles/{legacy.id}/preferences', headers=headers(), json={**payload, 'confirm_migration': True}).status_code == 422
    assert client.put(url, headers=headers(), json={**payload, 'funding_order': [route['id']]}).status_code == 422
    assert client.put(url, headers=headers(), json=payload).status_code == 200
    payload = {'monitor': True, 'repayment': False, 'funding_order': [], 'repayment_order': []}
    url = f'/api/bank-monitor/profiles/{legacy.id}/preferences'
    assert client.put(url, headers=headers(), json=payload).status_code == 409
    issues = next(p for p in client.get('/api/bank-monitor/profiles', headers=headers()).json()['profiles'] if p['id'] == legacy.id)['preferences']['review_items']
    response = client.put(url, headers=headers(), json={**payload, 'confirm_migration': True, 'removed_review_items': [item['id'] for item in issues]})
    assert response.status_code == 200
    assert response.json()['unified'] is True


def test_background_checks_do_not_confirm_migration(setup, db, monkeypatch):
    from app.models.bank_monitor import BankProfilePreferences
    from app.services.bank_profile_preferences import unified
    client, p, legacy = setup
    db.add(BankProfilePreferences(profile_id=p.id, tenant_id=1, settings={'confirmed': True, 'monitor': False, 'repayment': False, 'funding_order': [], 'repayment_order': [], 'review_required': []}))
    db.commit()
    monkeypatch.setattr(service, 'sync_profile', lambda db, profile: None)
    service.run_due_profiles(db, datetime(2026, 9, 28, 22, tzinfo=timezone.utc))
    assert db.query(BankProfileRun).filter_by(profile_id=p.id).count() == 0
    assert db.query(BankProfileRun).filter_by(profile_id=legacy.id).count() == 1
    assert unified(db, 1) is False


def test_profile_schedule_preserves_archived_rules_and_reserves(setup, db):
    from app.models.bank_monitor import BankProfilePreferences
    client, p, legacy = setup
    old = dict(db.get(BankMonitorConfig, 1).rules)
    for profile in (p, legacy):
        db.add(BankProfilePreferences(profile_id=profile.id, tenant_id=1, settings={'confirmed': True, 'monitor': True, 'repayment': False, 'funding_order': [], 'repayment_order': [], 'review_required': []}))
    account = db.query(BankAccountIdentity).filter_by(last4='3304').one()
    account.reserve_cents = 12345
    db.commit()
    response = client.put('/api/bank-monitor/profile-schedule', headers={'X-Tenant-ID': '1', 'X-Bank-Monitor-Action': 'save-settings'}, json={'enabled': False})
    assert response.status_code == 200
    assert db.get(BankMonitorConfig, 1).enabled is False
    assert db.get(BankMonitorConfig, 1).rules == old
    assert db.get(BankAccountIdentity, account.id).reserve_cents == 12345


def test_route_evaluation_never_creates_drafts(setup, db):
    from app.models.bank_monitor import BankProfilePreferences
    from app.services.bank_profile_preferences import evaluate
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    db.add(BankProfilePreferences(profile_id=p.id, tenant_id=1, settings={'confirmed': True, 'monitor': True, 'repayment': True, 'funding_order': [], 'repayment_order': [route['id']], 'review_required': []}))
    db.commit()
    result = evaluate(db, p, datetime(2026, 10, 2, 22, tzinfo=timezone.utc))
    assert result['routes'][0]['route_id'] == route['id']
    assert result['routes'][0]['status'] == 'evidence_required'
    assert result['transfers_executed'] is False
    assert db.query(BankTransferDraft).count() == 0


def test_account_order_survives_provider_reordering(setup, db, monkeypatch):
    client, p, _ = setup
    def account_ids():
        data = client.get('/api/bank-monitor/profiles', headers=headers()).json()
        accounts = next(profile for profile in data['profiles'] if profile['id'] == p.id)['accounts']
        return [(a['last4'], a['id']) for a in accounts]
    before = account_ids()
    assert [mask for mask, _ in before] == ['3304', '8264']
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', lambda token: [row('new-credit', '8264', 'credit', 1900), row('new-checking', '3304', amount=1100)])
    assert client.post(f'/api/bank-monitor/profiles/{p.id}/sync', headers=headers()).status_code == 200
    assert account_ids() == before


def test_rename_connection_preserves_access_accounts_and_routes(setup, db):
    client, profile, _ = setup
    route = resolve_and_route(client, db, profile)
    before = (profile.item_id, profile.encrypted_access_token)
    members = [(a.id, a.account_id) for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id).order_by(BankProfileAccount.id)]
    url = f'/api/bank-monitor/profiles/{profile.id}/name'
    assert client.put(url, headers=headers(2), json={'name': 'Other'}).status_code == 404
    assert client.put(url, headers={'X-Tenant-ID': '1'}, json={'name': 'Other'}).status_code == 403
    for name in ('', '   ', 'x' * 81):
        assert client.put(url, headers=headers(), json={'name': name}).status_code == 422
    response = client.put(url, headers=headers(), json={'name': '  Business banking  '})
    assert response.status_code == 200
    assert next(p for p in response.json()['profiles'] if p['id'] == profile.id)['name'] == 'Business banking'
    db.refresh(profile)
    assert (profile.item_id, profile.encrypted_access_token) == before
    assert [(a.id, a.account_id) for a in db.query(BankProfileAccount).filter_by(profile_id=profile.id).order_by(BankProfileAccount.id)] == members
    assert db.get(BankProfileRoute, route['id']).enabled is True


def test_opposite_route_permissions_remain_independent(setup, db):
    client, profile, _ = setup
    payment = resolve_and_route(client, db, profile)
    response = client.post('/api/bank-monitor/profiles/routes', headers=headers(), json={'profile_id': profile.id, 'source_id': payment['destination_id'], 'destination_id': payment['source_id'], 'bank_route_confirmed': True})
    assert response.status_code == 200
    draw = next(r for r in response.json()['routes'] if r['id'] != payment['id'])
    assert client.put(f"/api/bank-monitor/profiles/routes/{payment['id']}", headers=headers(), json={'enabled': False}).status_code == 200
    assert db.get(BankProfileRoute, payment['id']).enabled is False
    assert db.get(BankProfileRoute, draw['id']).enabled is True


def test_unavailable_payment_requires_specific_removal(setup, db):
    from app.models.bank_monitor import BankProfilePreferences
    client, profile, _ = setup
    route = resolve_and_route(client, db, profile)
    db.add(BankProfilePreferences(profile_id=profile.id, tenant_id=1, settings={'confirmed': True, 'monitor': True, 'repayment': True, 'funding_order': [], 'repayment_order': [route['id']], 'review_required': []}))
    db.get(BankProfileRoute, route['id']).enabled = False
    db.commit()
    payload = {'monitor': True, 'repayment': False, 'funding_order': [], 'repayment_order': [], 'confirm_migration': True}
    url = f'/api/bank-monitor/profiles/{profile.id}/preferences'
    assert client.put(url, headers=headers(), json=payload).status_code == 409
    data = client.get('/api/bank-monitor/profiles', headers=headers()).json()
    issue = next(p for p in data['profiles'] if p['id'] == profile.id)['preferences']['review_items'][0]
    assert '3304' in issue['label'] and '8264' in issue['label']
    payload['removed_review_items'] = [issue['id']]
    assert client.put(url, headers=headers(), json={**payload, 'repayment_order': [route['id']]}).status_code == 422
    assert client.put(url, headers=headers(), json=payload).status_code == 200
    assert db.get(BankProfileRoute, route['id']).enabled is False


def test_partial_legacy_removal_preserves_other_warnings(setup, db):
    client, _, legacy = setup
    config = db.get(BankMonitorConfig, 1)
    config.rules = {**config.rules, 'sources': [*config.rules['sources'], {'nickname': 'Visa', 'last4': '8539'}]}
    db.commit()
    payload = {'monitor': True, 'repayment': False, 'funding_order': [], 'repayment_order': [], 'confirm_migration': True, 'removed_review_items': ['funding:8539']}
    url = f'/api/bank-monitor/profiles/{legacy.id}/preferences'
    response = client.put(url, headers=headers(), json=payload)
    assert response.status_code == 200
    def remaining(data):
        return next(p for p in data['profiles'] if p['id'] == legacy.id)['preferences']['review_items']
    assert [i['id'] for i in remaining(response.json())] == ['funding:2829']
    assert [i['id'] for i in remaining(client.get('/api/bank-monitor/profiles', headers=headers()).json())] == ['funding:2829']
    payload['removed_review_items'] = ['funding:2829']
    assert remaining(client.put(url, headers=headers(), json=payload).json()) == []
    assert db.query(BankProfileRoute).count() == 0


@pytest.fixture
def financed_equipment(db):
    from app.models.truck import Truck
    from tests.test_investment_progress import asset
    trailer = Truck(tenant_id=1, name='HELOC Trailer', vin='VIN3142', vehicle_type='trailer', investment_plans=asset().investment_plans)
    db.add(trailer); db.commit()
    return trailer


def test_equipment_link_and_dedicated_draft_keep_payment_unconfirmed(setup, db, financed_equipment):
    from app.models.bank_monitor import BankEquipmentDraft
    from app.services.equipment_payments import summary
    from datetime import date
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    asset = financed_equipment
    link = client.put(f'/api/bank-monitor/profiles/equipment/{asset.id}/account', headers=headers(), json={'account_id': route['destination_id']})
    assert link.status_code == 200, link.text
    review = client.post(f"/api/bank-monitor/profiles/routes/{route['id']}/review", headers=headers()).json()
    response = client.post(f"/api/bank-monitor/profiles/reviews/{review['id']}/draft", headers=headers(), json={'amount_cents': 76646, 'equipment_asset_id': asset.id})
    assert response.status_code == 200, response.text
    draft = response.json()['draft']
    assert draft['equipment']['asset_id'] == asset.id
    assert draft['equipment']['name'] == asset.name
    assert draft['memo'].startswith('Rpy Trailer ')
    assert len(draft['memo']) <= 34
    assert db.query(BankEquipmentDraft).count() == 1
    assert summary(db, 1, asset, date.today())['payment_count'] == 0
    assert client.get('/api/bank-monitor/drafts', headers=headers()).json()[0]['equipment']['asset_id'] == asset.id
    repeated = client.post(f"/api/bank-monitor/profiles/routes/{route['id']}/review", headers=headers()).json()
    assert repeated['existing_draft']['id'] == draft['id']


def test_equipment_link_rejects_checking_and_foreign_assets(setup, db, financed_equipment):
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    asset = financed_equipment
    url = f'/api/bank-monitor/profiles/equipment/{asset.id}/account'
    assert client.put(url, headers=headers(), json={'account_id':route['source_id']}).status_code == 422
    asset.tenant_id = 2; db.commit()
    assert client.put(url, headers=headers(), json={'account_id':route['destination_id']}).status_code == 404


def test_equipment_draft_requires_link_and_preserves_cash_limit(setup, db, financed_equipment):
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    asset = financed_equipment
    review = client.post(f"/api/bank-monitor/profiles/routes/{route['id']}/review", headers=headers()).json()
    url = f"/api/bank-monitor/profiles/reviews/{review['id']}/draft"
    assert client.post(url, headers=headers(), json={'amount_cents':76646, 'equipment_asset_id':asset.id}).status_code == 409
    client.put(f'/api/bank-monitor/profiles/equipment/{asset.id}/account', headers=headers(), json={'account_id':route['destination_id']})
    assert client.post(url, headers=headers(), json={'amount_cents':90001, 'equipment_asset_id':asset.id}).status_code == 409
    assert db.query(BankTransferDraft).count() == 0


def test_equipment_cannot_pay_wrong_line_or_duplicate_from_another_checking(setup, db, financed_equipment):
    from app.models.bank_monitor import BankEquipmentAccount, BankEquipmentDraft, BankRepaymentRun
    client, p, _ = setup
    route = resolve_and_route(client, db, p)
    asset = financed_equipment
    review = client.post(f"/api/bank-monitor/profiles/routes/{route['id']}/review", headers=headers()).json()
    db.add(BankEquipmentAccount(asset_id=asset.id,tenant_id=1,account_id='different-credit',updated_at=datetime.now(timezone.utc)))
    db.commit()
    url=f"/api/bank-monitor/profiles/reviews/{review['id']}/draft"
    response=client.post(url,headers=headers(),json={'amount_cents':10000,'equipment_asset_id':asset.id})
    assert response.status_code==409
    link=db.get(BankEquipmentAccount,asset.id);link.account_id=route['destination_id']
    # An unfinished trailer payment from another checking blocks a second draft.
    other=BankTransferDraft(id='other-source-draft',tenant_id=1,charge_reference='other-source',amount_cents=10000,
        from_last4='9551',to_last4='8264',memo='Rpy Trailer',status='reviewed',created_at=datetime.now(timezone.utc))
    db.add(other)
    db.add(BankEquipmentDraft(draft_id=other.id,tenant_id=1,asset_id=asset.id,asset_name=asset.name,vin=asset.vin,account_id=route['destination_id']))
    db.commit()
    response=client.post(url,headers=headers(),json={'amount_cents':10000,'equipment_asset_id':asset.id})
    assert response.status_code==409
    assert 'already in progress' in response.json()['detail']
    assert db.query(BankTransferDraft).count()==1
    assert not db.get(BankRepaymentRun,review['id']).result.get('drafts_created')


def coverage_setup(setup, db, monkeypatch, pending=63686):
    from app.models.bank_monitor import BankProfilePreferences
    client, profile, _ = setup
    resolve_and_route(client, db, profile)
    checking = db.query(BankProfileAccount).filter_by(profile_id=profile.id, last4='3304').one()
    credit = db.query(BankProfileAccount).filter_by(profile_id=profile.id, last4='8264').one()
    db.get(BankAccountIdentity, checking.account_id).reserve_cents = 1000
    route = BankProfileRoute(id=str(uuid4()), tenant_id=1, profile_id=profile.id,
        source_id=credit.account_id, destination_id=checking.account_id, enabled=True)
    db.add(route)
    db.add(BankProfilePreferences(profile_id=profile.id, tenant_id=1, settings={'confirmed': True, 'monitor': True, 'repayment': False, 'funding_order': [route.id], 'repayment_order': [], 'review_required': []}))
    monkeypatch.setattr(plaid_bank, 'real_time_accounts', lambda token: [row('new-checking', '3304', amount=-340), row('new-credit', '8264', 'credit', 2000)])
    monkeypatch.setattr(plaid_bank, 'transaction_visibility', lambda token, mapping: {'pending_debit_cents': {key: pending if value['kind'] == 'checking' else 0 for key, value in mapping.items()}, 'pending_entries': {key: 1 for key in mapping}})
    service.sync_profile(db, profile); db.commit()
    return client, profile, route


# Whole-charge funding supersedes the former aggregate balance scenarios.
def charge_setup(setup, db, monkeypatch):
    client, profile, route = coverage_setup(setup, db, monkeypatch)
    entries = [dict(transaction_id=f'charge-{i}', pending_transaction_id=None, amount_cents=amount,
        description=f'Expense {i}', date=datetime.now(timezone.utc).date().isoformat(), pending=True,
        currency='USD', category='LOAN_PAYMENTS' if i==0 else 'TRANSFER_OUT') for i, amount in enumerate([28686, 35000])]
    monkeypatch.setattr(plaid_bank, 'transaction_visibility', lambda token, mapping: {
        'pending_debit_cents': {k:63686 if v['kind']=='checking' else 0 for k,v in mapping.items()},
        'pending_entries': {k:2 if v['kind']=='checking' else 0 for k,v in mapping.items()},
        'charge_details': {k:entries if v['kind']=='checking' else [] for k,v in mapping.items()}})
    service.sync_profile(db, profile); db.commit()
    return client, profile, route, entries


def test_daily_whole_charges_repeat_and_approval(setup, db, monkeypatch):
    client, profile, route, entries = charge_setup(setup, db, monkeypatch)
    now = datetime.now(timezone.utc).replace(hour=22, minute=0)
    service.run_due_profiles(db, now)
    drafts = db.query(BankTransferDraft).all()
    assert sorted(d.amount_cents for d in drafts) == [28686,35000]
    assert all(d.status == 'review_required' for d in drafts)
    service.run_due_profiles(db, now)
    assert db.query(BankTransferDraft).count() == 2
    for draft in drafts:
        assert client.post(f'/api/bank-monitor/drafts/{draft.id}/prepare', headers={**headers(),'X-Bank-Monitor-Action':'reviewed-transfer'}).status_code == 409
        response = client.post(f'/api/bank-monitor/profiles/drafts/{draft.id}/review', headers=headers())
        assert response.status_code == 200, response.text
        review = response.json(); path = f"/api/bank-monitor/profiles/reviews/{review['id']}/draft"
        assert client.post(path, headers=headers(), json={'amount_cents':draft.amount_cents}).status_code == 409
        assert client.post(path, headers=headers(), json={'amount_cents':draft.amount_cents-1,'coverage_confirmed':True}).status_code == 409
        r=client.post(path, headers=headers(), json={'amount_cents':draft.amount_cents,'coverage_confirmed':True})
        assert r.status_code == 200, r.text
        assert r.json()['draft']['id'] == draft.id
        assert client.post(path, headers=headers(), json={'amount_cents':draft.amount_cents,'coverage_confirmed':True}).status_code == 409


def test_skip_insufficient_source_and_never_split_charge(setup, db, monkeypatch):
    from app.services.bank_charge_funding import scheduled_drafts
    from app.models.bank_monitor import BankProfilePreferences
    _,profile,route,_=charge_setup(setup,db,monkeypatch)
    identity=BankAccountIdentity(id=str(uuid4()),tenant_id=1,institution_id=profile.institution_id,name='HELOC',last4='3062',kind='credit',reserve_cents=0)
    db.add(identity)
    db.add(BankProfileAccount(id=str(uuid4()),profile_id=profile.id,account_id=identity.id,provider_account_id='heloc',name='HELOC',last4='3062',kind='credit',subtype='home equity',active=True,balance={'available_cents':1164,'current_cents':9998836,'currency':'USD','pending_debit_cents':0}))
    small=BankProfileRoute(id=str(uuid4()),tenant_id=1,profile_id=profile.id,source_id=identity.id,destination_id=route.destination_id,enabled=True)
    db.add(small)
    prefs=db.get(BankProfilePreferences,profile.id);prefs.settings={**prefs.settings,'funding_order':[small.id,route.id]};db.commit()
    _,ids=scheduled_drafts(db,profile);db.commit()
    assert sorted(db.get(BankTransferDraft,id).amount_cents for id in ids)==[28686,35000]
    assert all(db.get(BankProfileDraft,id).route_id==route.id for id in ids)
    assert scheduled_drafts(db,profile)[1]==[]


def test_pending_posted_completion_identity(setup,db,monkeypatch):
    from app.services.bank_charge_funding import scheduled_drafts
    from app.models.bank_monitor import BankFundingCharge
    _,profile,_,entries=charge_setup(setup,db,monkeypatch)
    _,ids=scheduled_drafts(db,profile);db.commit()
    entries[0]={**entries[0],'transaction_id':'posted-0','pending_transaction_id':'charge-0','pending':False}
    service.sync_profile(db,profile);db.commit()
    assert db.query(BankFundingCharge).count()==2
    for id in ids: db.get(BankTransferDraft,id).status='bank_history_matched'
    db.commit()
    assert scheduled_drafts(db,profile)[1]==[]
    assert db.query(BankFundingCharge).filter_by(pending=False).one().draft_id in ids


def test_changed_and_removed_charge_blocks_old_review(setup,db,monkeypatch):
    from app.services.bank_charge_funding import scheduled_drafts
    client,profile,_,entries=charge_setup(setup,db,monkeypatch)
    _,ids=scheduled_drafts(db,profile);db.commit()
    id=next(id for id in ids if db.get(BankTransferDraft,id).amount_cents==28686)
    r=client.post(f'/api/bank-monitor/profiles/drafts/{id}/review',headers=headers()).json()
    entries[0]['amount_cents']=30000
    service.sync_profile(db,profile);db.commit()
    assert client.post(f"/api/bank-monitor/profiles/reviews/{r['id']}/draft",headers=headers(),json={'amount_cents':28686,'coverage_confirmed':True}).status_code==409
    entries.clear();service.sync_profile(db,profile);db.commit()
    assert client.post(f'/api/bank-monitor/profiles/drafts/{id}/review',headers=headers()).status_code==409


def test_manual_charge_duplicate_and_profile_binding(setup,db,monkeypatch):
    from app.models.bank_monitor import BankFundingCharge
    client,profile,route,entries=charge_setup(setup,db,monkeypatch)
    payload={'route_id':route.id,'reference':'invoice-55','description':'Repair expense','charge_date':datetime.now(timezone.utc).date().isoformat(),'amount_cents':50000,'confirmed_uncovered':True}
    r=client.post('/api/bank-monitor/profiles/charges/draft',headers=headers(),json=payload)
    assert r.status_code==200,r.text
    assert r.json()['draft']['charge']['description']=='Repair expense'
    assert db.get(BankProfileDraft,r.json()['draft']['id']).profile_id==profile.id
    assert client.post('/api/bank-monitor/profiles/charges/draft',headers=headers(),json=payload).status_code==409
    entries.append({**entries[0],'transaction_id':'manual-later','amount_cents':50000,'date':(datetime.now(timezone.utc).date()+timedelta(days=2)).isoformat()})
    service.sync_profile(db,profile);db.commit()
    assert db.query(BankFundingCharge).filter_by(reference='plaid:manual-later').one().status=='duplicate_review'


def test_no_historical_backfill_or_tracked_transfer_funding(setup,db,monkeypatch):
    from app.services.bank_charge_funding import ingest,proposals
    from app.models.bank_monitor import BankFundingCharge
    _,profile,route=coverage_setup(setup,db,monkeypatch)
    target=db.query(BankProfileAccount).filter_by(profile_id=profile.id,account_id=route.destination_id).one()
    e={'transaction_id':'old','amount_cents':1000,'description':'Old expense','date':'2026-01-01','pending':False,'currency':'USD','category':'GENERAL_MERCHANDISE'}
    own=BankTransferDraft(id=str(uuid4()),tenant_id=1,charge_reference='own-outgoing',amount_cents=1000,from_last4='3304',to_last4='8264',memo='Rpy ELIS own-transfer',status='bank_history_matched',created_at=datetime.now(timezone.utc))
    db.add(own);db.add(BankProfileDraft(draft_id=own.id,tenant_id=1,profile_id=profile.id,route_id=route.id,source_id=route.destination_id,destination_id=route.source_id));db.flush()
    ingest(db,profile,target,[e,{**e,'transaction_id':'internal','category':'TRANSFER_OUT','bank_description':'Regular Payment Rpy ELIS / own-transfer'}]);db.commit()
    assert db.query(BankFundingCharge).one().status=='historical'
    assert proposals(db,profile)==[]


def test_no_partial_charge_draft_when_all_sources_insufficient(setup,db,monkeypatch):
    from app.services.bank_charge_funding import scheduled_drafts
    _,profile,route,_=charge_setup(setup,db,monkeypatch)
    source=db.query(BankProfileAccount).filter_by(profile_id=profile.id,account_id=route.source_id).one()
    source.balance={**source.balance,'available_cents':12000};db.commit()
    coverage,ids=scheduled_drafts(db,profile)
    assert not ids
    assert sorted(c['uncovered_cents'] for c in coverage)==[28686,35000]


def test_shared_login_charge_feed_is_not_imported_twice(setup,db,monkeypatch):
    from app.services.bank_charge_funding import ingest,scheduled_drafts
    from app.models.bank_monitor import BankFundingCharge,BankProfilePreferences
    _,profile,route,entries=charge_setup(setup,db,monkeypatch)
    other=BankProfile(id=str(uuid4()),tenant_id=1,name='Other login',item_id='other-charges',institution_id=profile.institution_id,encrypted_access_token='other',status='synced',created_at=datetime.now(timezone.utc),last_checked_at=profile.last_checked_at)
    db.add(other)
    for member in db.query(BankProfileAccount).filter_by(profile_id=profile.id).all():
        copied=BankProfileAccount(id=str(uuid4()),profile_id=other.id,account_id=member.account_id,provider_account_id='other-'+member.provider_account_id,name=member.name,last4=member.last4,kind=member.kind,subtype=member.subtype,active=True,balance=member.balance)
        db.add(copied)
        if copied.kind=='checking':
            ingest(db,other,copied,[{**e,'transaction_id':'other-'+e['transaction_id']} for e in entries])
    r=BankProfileRoute(id=str(uuid4()),tenant_id=1,profile_id=other.id,source_id=route.source_id,destination_id=route.destination_id,enabled=True)
    db.add(r);db.add(BankProfilePreferences(profile_id=other.id,tenant_id=1,settings={'confirmed':True,'monitor':True,'repayment':False,'funding_order':[r.id],'repayment_order':[],'review_required':[]}));db.commit()
    assert db.query(BankFundingCharge).count()==2
    assert len(scheduled_drafts(db,profile)[1])==2
    assert scheduled_drafts(db,other)[1]==[]


def test_manual_full_charge_selection_and_tenant_scope(setup,db,monkeypatch):
    from app.models.bank_monitor import BankFundingCharge
    client,profile,route,_=charge_setup(setup,db,monkeypatch)
    charge=db.query(BankFundingCharge).filter_by(amount_cents=28686).one()
    r=client.post('/api/bank-monitor/profiles/charges/draft',headers=headers(),json={'route_id':route.id,'charge_id':charge.id})
    assert r.status_code==200,r.text
    assert r.json()['draft']['amount_cents']==28686
    assert client.post('/api/bank-monitor/profiles/charges/draft',headers=headers(),json={'route_id':route.id,'charge_id':charge.id}).status_code==409
    assert client.get('/api/bank-monitor/profiles/funding-charges',headers=headers(2)).status_code in {403,404}
    cancel=client.post(f"/api/bank-monitor/drafts/{r.json()['draft']['id']}/cancel",headers={**headers(),'X-Bank-Monitor-Action':'reviewed-transfer'})
    assert cancel.status_code==200
    from app.services.bank_charge_funding import scheduled_drafts
    _,ids=scheduled_drafts(db,profile)
    assert len(ids)==1  # cancelled charge is not silently recreated


def test_source_reservations_allow_only_complete_charges(setup,db,monkeypatch):
    from app.services.bank_charge_funding import scheduled_drafts
    _,profile,route,_=charge_setup(setup,db,monkeypatch)
    source=db.query(BankProfileAccount).filter_by(profile_id=profile.id,account_id=route.source_id).one()
    source.balance={**source.balance,'available_cents':50000};db.commit()
    coverage,ids=scheduled_drafts(db,profile)
    assert len(ids)==1
    assert db.get(BankTransferDraft,ids[0]).amount_cents in {28686,35000}
    assert sum(c['uncovered_cents'] for c in coverage) in {28686,35000}


def test_cancelled_charge_can_be_explicitly_requeued_but_completed_cannot(setup,db,monkeypatch):
    from app.models.bank_monitor import BankFundingCharge
    client,profile,route,_=charge_setup(setup,db,monkeypatch)
    charge=db.query(BankFundingCharge).filter_by(amount_cents=28686).one()
    payload={'route_id':route.id,'charge_id':charge.id,'confirmed_uncovered':True}
    first=client.post('/api/bank-monitor/profiles/charges/draft',headers=headers(),json=payload).json()['draft']
    client.post(f"/api/bank-monitor/drafts/{first['id']}/cancel",headers={**headers(),'X-Bank-Monitor-Action':'reviewed-transfer'})
    second=client.post('/api/bank-monitor/profiles/charges/draft',headers=headers(),json=payload)
    assert second.status_code==200,second.text
    assert second.json()['draft']['id']!=first['id']
    db.get(BankTransferDraft,second.json()['draft']['id']).status='bank_history_matched';db.commit()
    assert client.post('/api/bank-monitor/profiles/charges/draft',headers=headers(),json=payload).status_code==409


@pytest.mark.parametrize('description,label', [
    ('Empower', 'Empower'), ('Coinbase', 'Coinbase'),
    ('External Withdrawal PAYPAL / INSTANT TRANSFER', 'PAYPAL INSTANT'),
    ('Café & utilities payment', 'Cafe utilities'), ('💳', 'Charge'),
])
def test_charge_memo_contains_purpose_date_and_bank_safe_reference(description, label):
    import re
    from datetime import date
    from types import SimpleNamespace
    from app.services.bank_charge_funding import charge_memo
    charge = SimpleNamespace(description=description, charge_date=date(2026, 9, 28))
    memo = charge_memo(charge, '6c42726e-26c6-0000-0000-000000000000')
    assert memo.startswith(f'Cvr {label}')
    assert memo.endswith(' 09-28 6c42726e')
    assert len(memo) <= 34
    assert re.fullmatch(r'Cvr [A-Za-z0-9 ._-]{1,30}', memo)


def test_legacy_charge_memo_updated_during_review(setup, db, monkeypatch):
    from app.services.bank_charge_funding import scheduled_drafts
    client,profile,_,entries = charge_setup(setup,db,monkeypatch)
    _,ids = scheduled_drafts(db,profile)
    draft = db.get(BankTransferDraft,ids[0])
    assert draft.memo.startswith('Cvr Expense ')
    draft.memo = f'Cvr ELIS {draft.id[:13]}'
    db.commit()
    review = client.post(f'/api/bank-monitor/profiles/drafts/{draft.id}/review',headers=headers()).json()
    response = client.post(f"/api/bank-monitor/profiles/reviews/{review['id']}/draft",headers=headers(),json={'amount_cents':draft.amount_cents,'coverage_confirmed':True})
    assert response.status_code == 200, response.text
    assert response.json()['draft']['memo'].startswith('Cvr Expense ')
    assert response.json()['draft']['memo'].endswith(draft.id[:8])


@pytest.mark.parametrize('outcome,upgraded', [
    ('preparation_not_started', True), ('preparation_failed', False),
    ('prepared_awaiting_submission', False),
])
def test_charge_memo_only_changes_after_confirmed_pre_bank_cancellation(setup,db,monkeypatch,outcome,upgraded):
    from app.services.bank_charge_funding import scheduled_drafts
    client,profile,_,_=charge_setup(setup,db,monkeypatch)
    _,ids=scheduled_drafts(db,profile)
    draft=db.get(BankTransferDraft,ids[0])
    old=f'Cvr ELIS {draft.id[:13]}'
    draft.memo=old
    draft.status='preparation_requested'
    db.commit()
    response=client.post(f'/api/bank-monitor/drafts/{draft.id}/outcome',headers={**headers(),'X-Bank-Monitor-Action':'reviewed-transfer'},json={'status':outcome})
    assert response.status_code==200, response.text
    db.refresh(draft)
    assert (draft.memo != old) == upgraded
    if upgraded: assert draft.memo.startswith('Cvr Expense ')
    assert client.post(f'/api/bank-monitor/drafts/{draft.id}/outcome',headers={**headers(),'X-Bank-Monitor-Action':'reviewed-transfer'},json={'status':'preparation_not_started'}).status_code==409


def test_existing_ready_charge_gets_descriptive_memo_before_extension_dispatch(setup,db,monkeypatch):
    from app.services.bank_charge_funding import scheduled_drafts
    client,profile,_,_=charge_setup(setup,db,monkeypatch)
    _,ids=scheduled_drafts(db,profile)
    draft=db.get(BankTransferDraft,ids[0])
    draft.memo=f'Cvr ELIS {draft.id[:13]}'
    draft.status='reviewed'
    db.commit()
    response=client.post(f'/api/bank-monitor/drafts/{draft.id}/prepare',headers={**headers(),'X-Bank-Monitor-Action':'reviewed-transfer'})
    assert response.status_code==200, response.text
    assert response.json()['memo'].startswith('Cvr Expense ')
    assert response.json()['status']=='preparation_requested'
    assert response.json()['memo'].endswith(draft.id[:8])
    assert client.post(f'/api/bank-monitor/drafts/{draft.id}/prepare',headers={**headers(),'X-Bank-Monitor-Action':'reviewed-transfer'}).status_code==409


def test_full_charge_goes_directly_to_explicit_bank_assistant_review(setup,db,monkeypatch):
    from app.services.bank_charge_funding import scheduled_drafts
    client,profile,_,_=charge_setup(setup,db,monkeypatch)
    _,ids=scheduled_drafts(db,profile);db.commit()
    draft=db.get(BankTransferDraft,ids[0])
    path=f'/api/bank-monitor/drafts/{draft.id}/prepare-charge'
    action_headers={**headers(),'X-Bank-Monitor-Action':'reviewed-transfer'}
    # The generic path still requires the original approval flow.
    assert client.post(path.replace('/prepare-charge','/prepare'),headers=action_headers).status_code==409
    result=client.post(path,headers=action_headers)
    assert result.status_code==200,result.text
    assert result.json()['status']=='preparation_requested'
    assert result.json()['amount_cents']==draft.amount_cents
    assert result.json()['charge']['id']
    assert result.json()['memo'].startswith('Cvr Expense ')
    # Claimed for the extension's approval, never marked prepared or completed.
    assert client.post(path,headers=action_headers).status_code==409
    cancelled=client.post(path.replace('/prepare-charge','/outcome'),headers=action_headers,json={'status':'preparation_not_started'})
    assert cancelled.status_code==200
    assert db.get(BankTransferDraft,draft.id).status=='reviewed'


@pytest.mark.parametrize('invalid', ['changed_amount','insufficient_source','missing_charge','other_tenant','disabled_route'])
def test_direct_charge_review_preserves_validation_boundaries(setup,db,monkeypatch,invalid):
    from app.services.bank_charge_funding import scheduled_drafts
    from app.models.bank_monitor import BankFundingCharge
    client,profile,route,entries=charge_setup(setup,db,monkeypatch)
    _,ids=scheduled_drafts(db,profile);db.commit()
    draft=db.get(BankTransferDraft,ids[0])
    charge=db.query(BankFundingCharge).filter_by(draft_id=draft.id).one()
    if invalid=='changed_amount':
        for entry in entries:
            if entry['transaction_id'] in charge.provider_ids: entry['amount_cents']+=100
    if invalid=='insufficient_source': monkeypatch.setattr(service,'transfer_limit',lambda *a,**kw:{'limit_cents':0})
    if invalid=='missing_charge': db.delete(charge)
    if invalid=='disabled_route': route.enabled=False
    db.commit()
    response=client.post(f'/api/bank-monitor/drafts/{draft.id}/prepare-charge',headers={**headers(2 if invalid=='other_tenant' else 1),'X-Bank-Monitor-Action':'reviewed-transfer'})
    assert 400<=response.status_code<500,response.text
    db.refresh(draft)
    assert draft.status!='preparation_requested'
