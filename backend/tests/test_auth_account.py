"""Focused account login, reset, and authenticator regression tests."""
import time
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import database
from app.auth_security import _totp
from app.auth_utils import SESSION_COOKIE_NAME, verify_session_token
from app.database import Base, get_db
from app.main import app
from app.routers import auth


def test_recovery_email_over_https_without_smtp(monkeypatch):
    for name, value in {
        'APP_AUTH_PASSWORD': 'original-password', 'APP_AUTH_SECRET': 'independent-secret',
        'APP_AUTH_RECOVERY_EMAIL': 'owner@example.com', 'APP_PUBLIC_URL': 'https://hub.example.com',
        'APP_RESEND_API_KEY': 'test-api-key', 'APP_EMAIL_FROM': 'security@example.com',
    }.items():
        monkeypatch.setenv(name, value)
    for name in ('APP_SMTP_HOST', 'APP_SMTP_FROM', 'APP_SMTP_USERNAME', 'APP_SMTP_PASSWORD'):
        monkeypatch.delenv(name, raising=False)
    assert auth._recovery_configured()

    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'id': 'email-id'})

    original_client = httpx.Client
    monkeypatch.setattr(auth.httpx, 'Client', lambda **kwargs: original_client(transport=httpx.MockTransport(handler)))
    auth._send_reset_email('owner@example.com', 'single-use-token')
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == 'https://api.resend.com/emails'
    assert request.headers['Authorization'] == 'Bearer test-api-key'
    assert b'https://hub.example.com/reset-password?token=single-use-token' in request.content
    assert b'owner@example.com' in request.content

    auth._send_recovery_change_email('new@example.com', 'verification-token')
    assert len(requests) == 2
    assert b'https://hub.example.com/verify-recovery-email?token=verification-token' in requests[1].content
    assert b'Confirm your Elis Group Hub recovery email' in requests[1].content

    def rejected(request):
        return httpx.Response(403, json={'message': 'Sender is not verified'})
    monkeypatch.setattr(auth.httpx, 'Client', lambda **kwargs: original_client(transport=httpx.MockTransport(rejected)))
    with pytest.raises(httpx.HTTPStatusError):
        auth._send_reset_email('owner@example.com', 'single-use-token')


def test_recovery_capabilities_only_expose_masked_email(monkeypatch):
    for name, value in {
        'APP_AUTH_PASSWORD': 'original-password', 'APP_AUTH_SECRET': 'independent-secret',
        'APP_AUTH_RECOVERY_EMAIL': 'longowneraddress@example.com', 'APP_PUBLIC_URL': 'https://hub.example.com',
        'APP_RESEND_API_KEY': 'test-api-key', 'APP_EMAIL_FROM': 'security@example.com',
    }.items():
        monkeypatch.setenv(name, value)
    class EmptyDb:
        def get(self, *_args):
            return None
    response = auth.capabilities(db=EmptyDb())
    assert response == {'password_recovery': True, 'recovery_email_hint': 'l••••••s@example.com'}
    assert 'longowneraddress' not in str(response)

    monkeypatch.delenv('APP_RESEND_API_KEY')
    monkeypatch.delenv('APP_SMTP_HOST', raising=False)
    assert auth.capabilities(db=EmptyDb()) == {'password_recovery': False, 'recovery_email_hint': None}


def test_recovery_email_change_requires_password_and_new_inbox_confirmation(monkeypatch):
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(database, 'SessionLocal', sessions)
    for name, value in {
        'APP_AUTH_USERNAME': 'owner@example.com', 'APP_AUTH_PASSWORD': 'original-password',
        'APP_AUTH_SECRET': 'independent-session-secret', 'APP_AUTH_RECOVERY_EMAIL': 'oldaddress@example.com',
        'APP_PUBLIC_URL': 'https://hub.example.com', 'APP_RESEND_API_KEY': 'test-api-key',
        'APP_EMAIL_FROM': 'security@example.com',
    }.items():
        monkeypatch.setenv(name, value)
    sent = []
    monkeypatch.setattr(auth, '_send_recovery_change_email', lambda email, token: sent.append((email, token)))
    reset_sent = []
    monkeypatch.setattr(auth, '_send_reset_email', lambda email, token: reset_sent.append(email))

    def override_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            assert client.get('/api/auth/recovery-email').status_code == 401
            assert client.post('/api/auth/login', json={
                'username': 'owner@example.com', 'password': 'original-password',
            }).status_code == 200
            endpoint = '/api/auth/recovery-email/change-request'
            wrong = client.post(endpoint, json={'current_password': 'wrong', 'new_email': 'newaddress@example.com'})
            assert wrong.status_code == 401
            requested = client.post(endpoint, json={'current_password': 'original-password', 'new_email': 'newaddress@example.com'})
            assert requested.status_code == 200
            assert sent[0][0] == 'newaddress@example.com'
            assert client.get('/api/auth/recovery-email').json() == {
                'email': 'oldaddress@example.com', 'pending_email_hint': 'n••••••s@example.com',
            }
            assert client.get('/api/auth/capabilities').json()['recovery_email_hint'] == 'o••••••s@example.com'
            token = sent[0][1]
            assert client.post('/api/auth/recovery-email/confirm', json={'token': 'x' * 32}).status_code == 400
            assert client.post('/api/auth/recovery-email/confirm', json={'token': token}).status_code == 200
            assert client.post('/api/auth/recovery-email/confirm', json={'token': token}).status_code == 400
            assert client.get('/api/auth/recovery-email').json() == {
                'email': 'newaddress@example.com', 'pending_email_hint': None,
            }
            assert client.get('/api/auth/capabilities').json()['recovery_email_hint'] == 'n••••••s@example.com'
            client.post('/api/auth/password/reset-request', json={'email': 'oldaddress@example.com'})
            assert reset_sent == []
            client.post('/api/auth/password/reset-request', json={'email': 'newaddress@example.com'})
            assert reset_sent == ['newaddress@example.com']

            changed = client.post('/api/auth/password/change', json={
                'current_password': 'original-password', 'new_password': 'replacement-password-123',
            })
            assert changed.status_code == 200
            assert client.get('/api/auth/recovery-email').status_code == 200
            client.cookies.clear()
            assert client.post('/api/auth/login', json={
                'username': 'owner@example.com', 'password': 'original-password',
            }).status_code == 401
            assert client.post('/api/auth/login', json={
                'username': 'owner@example.com', 'password': 'replacement-password-123',
            }).status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_remember_reset_and_mfa(monkeypatch):
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(database, 'SessionLocal', sessions)
    for name, value in {
        'APP_AUTH_USERNAME': 'owner@example.com', 'APP_AUTH_PASSWORD': 'original-password',
        'APP_AUTH_SECRET': 'independent-session-secret', 'APP_AUTH_RECOVERY_EMAIL': 'owner@example.com',
        'APP_SMTP_HOST': 'smtp.example.com', 'APP_SMTP_FROM': 'security@example.com',
        'APP_PUBLIC_URL': 'https://hub.example.com',
    }.items():
        monkeypatch.setenv(name, value)
    sent = []
    monkeypatch.setattr(auth, '_send_reset_email', lambda email, token: sent.append((email, token)))

    def override_db():
        with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            login = client.post('/api/auth/login', json={
                'username': 'owner@example.com', 'password': 'original-password', 'remember': True,
            })
            assert login.status_code == 200
            assert 'Max-Age=604800' in login.headers['set-cookie']
            old_token = client.cookies.get(SESSION_COOKIE_NAME)
            assert verify_session_token(old_token)[0]

            unknown = client.post('/api/auth/password/reset-request', json={'email': 'someone@example.com'})
            known = client.post('/api/auth/password/reset-request', json={'email': 'owner@example.com'})
            assert unknown.status_code == known.status_code == 200
            assert unknown.json() == known.json()
            assert len(sent) == 1
            token = sent[0][1]
            reset = client.post('/api/auth/password/reset', json={'token': token, 'password': 'replacement-password-123'})
            assert reset.status_code == 200
            assert not verify_session_token(old_token)[0]
            assert client.post('/api/auth/password/reset', json={'token': token, 'password': 'another-password-123'}).status_code == 400
            assert client.post('/api/auth/login', json={'username': 'owner@example.com', 'password': 'original-password'}).status_code == 401
            monkeypatch.delenv('APP_AUTH_PASSWORD')
            assert client.post('/api/auth/login', json={'username': 'owner@example.com', 'password': 'replacement-password-123'}).status_code == 200

            setup = client.post('/api/auth/mfa/setup', json={'password': 'replacement-password-123'})
            assert setup.status_code == 200
            code = _totp(setup.json()['secret'], time.time_ns() // 30_000_000_000)
            confirm = client.post('/api/auth/mfa/confirm', json={'code': code})
            assert confirm.status_code == 200
            recovery = confirm.json()['recovery_codes'][0]
            assert len(confirm.json()['recovery_codes']) == 8
            client.cookies.clear()
            challenge = client.post('/api/auth/login', json={'username': 'owner@example.com', 'password': 'replacement-password-123'})
            assert challenge.status_code == 202
            assert SESSION_COOKIE_NAME not in client.cookies
            assert client.post('/api/auth/login', json={'username': 'owner@example.com', 'password': 'replacement-password-123', 'mfa_code': recovery}).status_code == 200
            client.cookies.clear()
            assert client.post('/api/auth/login', json={'username': 'owner@example.com', 'password': 'replacement-password-123', 'mfa_code': recovery}).status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
