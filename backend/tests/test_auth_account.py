"""Focused account login, reset, and authenticator regression tests."""
import time
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
