"""Browser response minimization and independently authorized bank detail access."""
import copy
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import database
from app.auth_utils import SESSION_COOKIE_NAME, create_session_token
from app.database import get_db
from app.models.auth_account import AuthAccount
from app.models.tenant import Tenant
from app.routers import tenants


ACCOUNTS = [
    {'bank_name': 'Example Bank', 'account_type': 'checking',
     'account_number': '123456789012', 'routing_number': '987654321',
     'legacy_secret': 'must-never-be-serialized'},
    {'bank_name': 'Other Bank', 'account_number': '876543210987', 'routing_number': '112233445'},
]
WRITABLE_ACCOUNTS = [{k: v for k, v in account.items() if k != 'legacy_secret'} for account in ACCOUNTS]


@pytest.fixture
def bank_client(db, monkeypatch):
    # A router-only app proves sensitive access does not rely on the shell middleware.
    app = FastAPI()
    app.include_router(tenants.router, prefix='/api/tenants')
    app.dependency_overrides[get_db] = lambda: db
    monkeypatch.setattr(database, 'SessionLocal', sessionmaker(bind=db.bind))
    monkeypatch.setenv('APP_AUTH_USERNAME', 'bank-owner')
    monkeypatch.setenv('APP_AUTH_SECRET', 'synthetic-bank-test-session-secret')
    monkeypatch.setenv('APP_AUTH_TENANT_IDS', '1')
    db.get(Tenant, 1).bank_accounts = copy.deepcopy(ACCOUNTS)
    db.add(Tenant(id=2, name='Other Business', bank_accounts=copy.deepcopy(ACCOUNTS)))
    db.commit()
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, create_session_token('bank-owner'))
        yield client


def access(client, action='show', tenant_id=1, **fields):
    body = {'action': action}
    if action != 'edit':
        body.update(account_index=0, field='account_number')
    body.update(fields)
    return client.post(f'/api/tenants/{tenant_id}/bank-details', json=body,
                       headers={'X-Bank-Details-Action': action})


def assert_summary(response):
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    for account in ACCOUNTS:
        assert account['account_number'] not in response.text
        assert account['routing_number'] not in response.text
    assert 'must-never-be-serialized' not in response.text
    data = response.json()
    if isinstance(data, list):
        data = data[0]
    bank = data['bank_accounts'][0]
    assert bank['account_number_masked'] == '••••9012'
    assert bank['routing_number_masked'] == '••••4321'
    assert 'account_number' not in bank
    assert 'routing_number' not in bank


@pytest.mark.parametrize('path', ['/api/tenants', '/api/tenants/', '/api/tenants/1'])
def test_reads_only_return_allowlisted_masked_details(bank_client, db, path):
    assert_summary(bank_client.get(path))
    assert db.get(Tenant, 1).bank_accounts == ACCOUNTS


@pytest.mark.parametrize('path', ['/api/tenants', '/api/tenants/'])
def test_create_response_is_masked(bank_client, path):
    assert_summary(bank_client.post(path, json={'name': 'Created Business', 'bank_accounts': WRITABLE_ACCOUNTS}))


def test_update_response_masked_and_unrelated_update_preserves_numbers(bank_client, db):
    assert_summary(bank_client.put('/api/tenants/1', json={'legal_name': 'New Legal Name'}))
    assert db.get(Tenant, 1).bank_accounts == ACCOUNTS
    assert_summary(bank_client.put('/api/tenants/1', json={'bank_accounts': WRITABLE_ACCOUNTS}))
    assert db.get(Tenant, 1).bank_accounts == WRITABLE_ACCOUNTS
    assert bank_client.put('/api/tenants/1', json={'bank_accounts': []}).json()['bank_accounts'] == []
    assert db.get(Tenant, 1).bank_accounts == []


@pytest.mark.parametrize('accounts', [None, [], [{'account_number': '1234', 'routing_number': '12'}],
                                     [{'account_number': ' 1234 ', 'routing_number': ' 12 '}]])
def test_empty_and_short_values_cannot_leak(bank_client, db, accounts):
    db.get(Tenant, 1).bank_accounts = accounts
    db.commit()
    response = bank_client.get('/api/tenants/1')
    assert response.status_code == 200
    if accounts:
        assert response.json()['bank_accounts'][0]['account_number_masked'] == '••••'
        assert response.json()['bank_accounts'][0]['routing_number_masked'] == '••••'
    else:
        assert response.json()['bank_accounts'] == []


@pytest.mark.parametrize('action', ['show', 'copy'])
@pytest.mark.parametrize('field', ['account_number', 'routing_number'])
def test_show_copy_return_only_requested_number(bank_client, action, field):
    response = access(bank_client, action, account_index=1, field=field)
    assert response.status_code == 200
    assert response.json() == {'value': ACCOUNTS[1][field]}
    assert response.headers['cache-control'] == 'private, no-store'


def test_edit_is_explicit_and_excludes_unknown_stored_fields(bank_client):
    response = access(bank_client, 'edit')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'private, no-store'
    assert response.json()['bank_accounts'][0] == WRITABLE_ACCOUNTS[0]
    assert 'legacy_secret' not in response.text
    assert bank_client.get('/api/tenants/1/bank-details').status_code == 405


def test_edit_normalizes_legacy_null_and_numeric_fields(bank_client, db):
    db.get(Tenant, 1).bank_accounts = [{'bank_name': None, 'account_number': 123456789012, 'routing_number': None}]
    db.commit()
    response = access(bank_client, 'edit')
    assert response.status_code == 200
    assert response.json()['bank_accounts'] == [{'bank_name': '', 'account_type': None,
                                               'account_number': '123456789012', 'routing_number': ''}]


@pytest.mark.parametrize('mode', ['missing', 'malformed', 'wrong-user', 'unconfigured', 'revoked', 'expired'])
def test_reveal_rejects_invalid_session_even_without_shell_auth(bank_client, db, monkeypatch, mode):
    if mode == 'missing':
        bank_client.cookies.clear()
    elif mode == 'malformed':
        bank_client.cookies.set(SESSION_COOKIE_NAME, 'not-a-session')
    elif mode == 'wrong-user':
        bank_client.cookies.set(SESSION_COOKIE_NAME, create_session_token('different-user'))
    elif mode == 'unconfigured':
        monkeypatch.delenv('APP_AUTH_USERNAME')
        monkeypatch.setenv('ELIS_FINANCE_LOCAL_TENANTS', '1')
    elif mode == 'revoked':
        db.add(AuthAccount(id=1, session_version=1))
        db.commit()
    elif mode == 'expired':
        monkeypatch.setattr('app.auth_utils.time.time', lambda: time.time_ns() // 1_000_000_000 + 8 * 86400)
    response = access(bank_client, 'edit')
    assert response.status_code == 401
    assert 'bank_accounts' not in response.text


@pytest.mark.parametrize('mode', ['foreign', 'inactive', 'missing', 'empty-allowlist'])
def test_reveal_requires_server_authorized_active_business(bank_client, db, monkeypatch, mode):
    tenant_id = 1
    if mode == 'foreign':
        tenant_id = 2
    elif mode == 'inactive':
        db.get(Tenant, 1).is_active = False
        db.commit()
    elif mode == 'missing':
        tenant_id = 123
        monkeypatch.setenv('APP_AUTH_TENANT_IDS', '123')
    else:
        monkeypatch.delenv('APP_AUTH_TENANT_IDS')
    response = access(bank_client, 'edit', tenant_id=tenant_id)
    assert response.status_code == 404
    assert response.json() == {'detail': 'Business unavailable.'}


def test_path_not_current_switcher_controls_authorized_business(bank_client, monkeypatch):
    monkeypatch.setenv('APP_AUTH_TENANT_IDS', '1, 2')
    response = bank_client.post('/api/tenants/2/bank-details', json={'action': 'edit'},
        headers={'X-Bank-Details-Action': 'edit', 'X-Tenant-ID': '1'})
    assert response.status_code == 200
    monkeypatch.setenv('APP_AUTH_TENANT_IDS', '1')
    assert access(bank_client, 'edit', tenant_id=2).status_code == 404


def test_missing_action_header_and_bad_selectors_cannot_reveal(bank_client):
    assert bank_client.post('/api/tenants/1/bank-details', json={'action': 'edit'}).status_code == 403
    assert access(bank_client, account_index=999).status_code == 404
    assert access(bank_client, account_index=-1).status_code == 422
    assert access(bank_client, field='legacy_secret').status_code == 422
    assert access(bank_client, 'edit', tenant_id_override=2).status_code == 422


def test_masked_roundtrip_cannot_overwrite_saved_numbers(bank_client, db):
    summaries = bank_client.get('/api/tenants/1').json()['bank_accounts']
    response = bank_client.put('/api/tenants/1', json={'bank_accounts': summaries})
    assert response.status_code == 422
    masked_input = copy.deepcopy(WRITABLE_ACCOUNTS)
    masked_input[0]['account_number'] = '••••9012'
    assert bank_client.put('/api/tenants/1', json={'bank_accounts': masked_input}).status_code == 422
    assert db.get(Tenant, 1).bank_accounts == ACCOUNTS


def test_bank_write_also_requires_authorization(bank_client, db):
    response = bank_client.put('/api/tenants/2', json={'bank_accounts': []})
    assert response.status_code == 404
    assert db.get(Tenant, 2).bank_accounts == ACCOUNTS


def test_validation_errors_do_not_echo_submitted_numbers(bank_client):
    invalid_account = {'bank_name': 'Example', 'account_number': 123456789012, 'routing_number': 987654321}
    for response in [
        bank_client.post('/api/tenants', json={'name': 'Invalid', 'bank_accounts': [invalid_account]}),
        bank_client.put('/api/tenants/1', json={'bank_accounts': [invalid_account]}),
    ]:
        assert response.status_code == 422
        assert '123456789012' not in response.text
        assert '987654321' not in response.text
        assert response.headers['cache-control'] == 'private, no-store'
