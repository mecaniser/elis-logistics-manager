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


def test_coverage_pending_ambiguity_requires_review(setup, db, monkeypatch):
    from app.services.bank_coverage import proposals
    client, profile, route = coverage_setup(setup, db, monkeypatch)
    suggestion = proposals(db, profile)[0]
    assert suggestion['minimum_cents'] == 35000
    assert suggestion['possible_cents'] == 98686
    assert suggestion['pending_review_required'] is True
    assert db.query(BankTransferDraft).count() == 0
    review = client.post(f'/api/bank-monitor/profiles/routes/{route.id}/review', headers=headers()).json()
    assert review['coverage']['minimum_cents'] == 35000
    path = f"/api/bank-monitor/profiles/reviews/{review['id']}/draft"
    assert client.post(path, headers=headers(), json={'amount_cents': 35000}).status_code == 409
    accepted = client.post(path, headers=headers(), json={'amount_cents': 35000, 'coverage_confirmed': True})
    assert accepted.status_code == 200, accepted.text
    assert db.query(BankTransferDraft).one().status == 'reviewed'
    assert client.post(path, headers=headers(), json={'amount_cents': 35000, 'coverage_confirmed': True}).status_code == 409
    assert proposals(db, profile)[0]['minimum_cents'] == 0  # existing incoming draft deducted


def test_coverage_without_pending_and_stale_review(setup, db, monkeypatch):
    from app.services.bank_coverage import proposals
    client, profile, route = coverage_setup(setup, db, monkeypatch, pending=0)
    suggestion = proposals(db, profile)[0]
    assert suggestion['minimum_cents'] == suggestion['possible_cents'] == 35000
    assert suggestion['pending_review_required'] is False
    profile.last_checked_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()
    assert not proposals(db, profile)[0]['routes']
    assert proposals(db, profile, allow_stale=True)[0]['routes']
    review = client.post(f'/api/bank-monitor/profiles/routes/{route.id}/review', headers=headers()).json()
    # A concurrent incoming transfer through another route must reduce the need.
    db.add(BankTransferDraft(id=str(uuid4()), tenant_id=1, charge_reference='test incoming', amount_cents=35000, from_last4='9551', to_last4='3304', memo='test', status='reviewed', created_at=datetime.now(timezone.utc)))
    db.commit()
    response = client.post(f"/api/bank-monitor/profiles/reviews/{review['id']}/draft", headers=headers(), json={'amount_cents': 35000, 'coverage_confirmed': True})
    assert response.status_code == 409


def test_coverage_pending_already_in_available_not_added_twice(setup, db, monkeypatch):
    from app.services.bank_coverage import proposals
    _, profile, _ = coverage_setup(setup, db, monkeypatch)
    checking = db.query(BankProfileAccount).filter_by(profile_id=profile.id, last4='3304').one()
    checking.balance = {**checking.balance, 'current_cents': 29686, 'available_cents': -34000}
    db.commit()
    value = proposals(db, profile)[0]
    assert value['minimum_cents'] == value['possible_cents'] == 35000
    assert value['pending_review_required'] is False


def test_daily_run_saves_coverage_proposal_without_creating_transfer(setup, db, monkeypatch):
    from app.models.bank_monitor import BankProfilePreferences
    _, profile, _ = coverage_setup(setup, db, monkeypatch, pending=0)
    now = datetime.now(timezone.utc).replace(hour=22, minute=0)
    service.run_due_profiles(db, now)
    result = db.get(BankProfilePreferences, profile.id).last_evaluation
    assert result['status'] == 'coverage_review_required'
    assert result['coverage'][0]['minimum_cents'] == 35000
    assert result['transfers_executed'] is False
    assert db.query(BankTransferDraft).count() == 0
    service.run_due_profiles(db, now)
    assert db.query(BankProfileRun).filter_by(profile_id=profile.id).count() == 1
