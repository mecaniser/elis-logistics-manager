"""
Auth router for session-based login/logout.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from email.message import EmailMessage
from urllib.parse import quote, urlsplit
import hashlib
import hmac
import httpx
import logging
import os
import secrets
import smtplib
import time

from app.auth_security import consume_recovery_code, decrypt_secret, encrypt_secret, hash_password, new_recovery_codes, new_totp_secret, totp_uri, verify_password, verify_totp
from app.database import SessionLocal, get_db
from app.models.auth_account import AuthAccount

from app.auth_utils import (
    SESSION_COOKIE_NAME,
    SESSION_DURATION_SECONDS,
    REMEMBER_DURATION_SECONDS,
    create_session_token,
    verify_session_token,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str = Field(max_length=254)
    password: str = Field(max_length=1024)
    remember: bool = False
    mfa_code: str | None = None


class RecoveryRequest(BaseModel):
    email: str = Field(max_length=254)


class ResetRequest(BaseModel):
    token: str = Field(min_length=30, max_length=256)
    password: str = Field(min_length=12, max_length=128)


class PasswordRequest(BaseModel):
    password: str


class MfaConfirmRequest(BaseModel):
    code: str = Field(pattern=r'^\d{6}$')


def _account(db: Session) -> AuthAccount:
    account = db.get(AuthAccount, 1)
    if not account:
        account = AuthAccount(id=1, session_version=0)
        db.add(account)
        db.flush()
    return account


def _password_matches(password: str, account: AuthAccount | None) -> bool:
    if account and account.password_hash:
        return verify_password(password, account.password_hash)
    expected = os.getenv('APP_AUTH_PASSWORD') or ''
    return bool(expected) and hmac.compare_digest(password, expected)


def _set_cookie(response: Response, username: str, remember: bool = False) -> None:
    token = create_session_token(username, remember)
    if not token:
        raise HTTPException(500, 'Unable to issue session token.')
    response.set_cookie(key=SESSION_COOKIE_NAME, value=token, httponly=True, samesite='lax',
                        secure=os.getenv('APP_AUTH_COOKIE_SECURE', 'false').lower() == 'true',
                        max_age=REMEMBER_DURATION_SECONDS if remember else SESSION_DURATION_SECONDS, path='/')


def _require_login(request: Request) -> str:
    expected = os.getenv('APP_AUTH_USERNAME')
    valid, username = verify_session_token(request.cookies.get(SESSION_COOKIE_NAME, ''))
    if not expected or not valid or username != expected:
        raise HTTPException(401, 'Sign in to manage account security.')
    return username


def _recovery_configured() -> bool:
    configured = all(os.getenv(name) for name in ('APP_AUTH_RECOVERY_EMAIL', 'APP_PUBLIC_URL'))
    resend_ready = all(os.getenv(name) for name in ('APP_RESEND_API_KEY', 'APP_EMAIL_FROM'))
    smtp_ready = all(os.getenv(name) for name in ('APP_SMTP_HOST', 'APP_SMTP_FROM'))
    credentials_complete = bool(os.getenv('APP_SMTP_USERNAME')) == bool(os.getenv('APP_SMTP_PASSWORD'))
    url = urlsplit(os.getenv('APP_PUBLIC_URL', ''))
    url_safe = url.scheme == 'https' and bool(url.netloc) and not url.username and not url.password and not url.path.strip('/')
    secret = os.getenv('APP_AUTH_SECRET')
    separate_secret = bool(secret) and secret != os.getenv('APP_AUTH_PASSWORD')
    return configured and (resend_ready or (smtp_ready and credentials_complete)) and url_safe and separate_secret


def _login_failed(account: AuthAccount, db: Session) -> None:
    account.failed_login_count = (account.failed_login_count or 0) + 1
    if account.failed_login_count >= 5:
        account.login_retry_after = int(time.time()) + 60
        account.failed_login_count = 0
    db.commit()


def _send_reset_email(email: str, token: str) -> None:
    link = f"{os.environ['APP_PUBLIC_URL'].rstrip('/')}/reset-password?token={quote(token)}"
    body = ('A password reset was requested for your Elis Group Hub account.\n\n'
            f'Use this link within 20 minutes: {link}\n\n'
            'If you did not request this, ignore this email. Your password has not changed.')
    if os.getenv('APP_RESEND_API_KEY') and os.getenv('APP_EMAIL_FROM'):
        with httpx.Client(timeout=10) as client:
            response = client.post('https://api.resend.com/emails',
                                   headers={'Authorization': f"Bearer {os.environ['APP_RESEND_API_KEY']}",
                                            'Idempotency-Key': hashlib.sha256(token.encode()).hexdigest()},
                                   json={'from': os.environ['APP_EMAIL_FROM'], 'to': [email],
                                         'subject': 'Reset your Elis Group Hub password', 'text': body})
            response.raise_for_status()
        return
    message = EmailMessage()
    message['Subject'] = 'Reset your Elis Group Hub password'
    message['From'] = os.environ['APP_SMTP_FROM']
    message['To'] = email
    message.set_content(body)
    port = int(os.getenv('APP_SMTP_PORT', '587'))
    smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    with smtp_class(os.environ['APP_SMTP_HOST'], port, timeout=10) as smtp:
        if port != 465:
            smtp.starttls()
        if os.getenv('APP_SMTP_USERNAME'):
            smtp.login(os.environ['APP_SMTP_USERNAME'], os.environ['APP_SMTP_PASSWORD'])
        smtp.send_message(message)


def _deliver_reset_email(email: str, token: str) -> None:
    try:
        _send_reset_email(email, token)
    except (OSError, smtplib.SMTPException, httpx.HTTPError, KeyError, ValueError):
        logger.exception('Password reset email delivery failed')
        # An undelivered link should not remain valid. Never log its token.
        with SessionLocal() as db:
            account = db.get(AuthAccount, 1)
            digest = hashlib.sha256(token.encode()).hexdigest()
            if account and account.reset_token_hash and hmac.compare_digest(account.reset_token_hash, digest):
                account.reset_token_hash = None
                account.reset_expires_at = None
                db.commit()


@router.post("/login")
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """
    Validate credentials and issue a signed session cookie.
    """
    expected_user = os.getenv("APP_AUTH_USERNAME")
    expected_pass = os.getenv("APP_AUTH_PASSWORD")

    account = _account(db)
    if not (expected_user and (expected_pass or account.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured on the server.",
        )

    if account.login_retry_after and account.login_retry_after > int(time.time()):
        raise HTTPException(429, 'Too many sign-in attempts. Try again in one minute.')
    if not hmac.compare_digest(data.username, expected_user) or not _password_matches(data.password, account):
        _login_failed(account, db)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
        )
    if account and account.mfa_secret:
        if not data.mfa_code:
            response.status_code = 202
            return {'mfa_required': True}
        if not verify_totp(decrypt_secret(account.mfa_secret), data.mfa_code):
            remaining = consume_recovery_code(account.recovery_code_hashes, data.mfa_code)
            if remaining is None:
                _login_failed(account, db)
                raise HTTPException(401, 'Incorrect authenticator or recovery code.')
            account.recovery_code_hashes = remaining
    account.failed_login_count = 0
    account.login_retry_after = None
    db.commit()
    _set_cookie(response, data.username, data.remember)
    return {"message": "Login successful"}


@router.post("/logout")
async def logout(response: Response):
    """
    Clear session cookie.
    """
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )
    return {"message": "Logged out"}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    """
    Return authenticated user based on session cookie.
    """
    # The API middleware deliberately allows unauthenticated local development
    # when credentials have not been configured.  Return the same state here
    # so the frontend does not strand local users on the login screen.
    account = db.get(AuthAccount, 1)
    if not (os.getenv("APP_AUTH_USERNAME") or os.getenv("APP_AUTH_PASSWORD") or (account and account.password_hash)):
        return {"username": "local-dev", "authentication_enabled": False}

    token = request.cookies.get(SESSION_COOKIE_NAME)
    valid, username = verify_session_token(token) if token else (False, None)

    if not valid or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return {"username": username}


@router.get('/capabilities')
def capabilities():
    return {'password_recovery': _recovery_configured()}


@router.post('/password/reset-request')
def reset_request(data: RecoveryRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not _recovery_configured():
        raise HTTPException(503, 'Password recovery is not configured. Contact the account administrator.')
    generic = {'message': 'If this is the recovery email for the account, a reset link will be sent.'}
    expected = os.environ['APP_AUTH_RECOVERY_EMAIL']
    if not hmac.compare_digest(data.email.strip().lower(), expected.strip().lower()):
        return generic
    account = _account(db)
    now = int(time.time())
    if account.reset_requested_at and now - account.reset_requested_at < 60:
        return generic
    token = secrets.token_urlsafe(32)
    account.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
    account.reset_expires_at = now + 20 * 60
    account.reset_requested_at = now
    db.commit()
    background_tasks.add_task(_deliver_reset_email, expected, token)
    return generic


@router.post('/password/reset')
def reset_password(data: ResetRequest, db: Session = Depends(get_db)):
    if not os.getenv('APP_AUTH_SECRET') or os.getenv('APP_AUTH_SECRET') == os.getenv('APP_AUTH_PASSWORD'):
        raise HTTPException(503, 'Password recovery is not configured.')
    account = db.get(AuthAccount, 1)
    digest = hashlib.sha256(data.token.encode()).hexdigest()
    if (not account or not account.reset_token_hash or
            not hmac.compare_digest(digest, account.reset_token_hash) or
            not account.reset_expires_at or account.reset_expires_at <= int(time.time())):
        raise HTTPException(400, 'This reset link is invalid or has expired.')
    account.password_hash = hash_password(data.password)
    account.session_version += 1
    account.failed_login_count = 0
    account.login_retry_after = None
    account.reset_token_hash = None
    account.reset_expires_at = None
    db.commit()
    return {'message': 'Password updated. Sign in with your new password.'}


@router.get('/mfa')
def mfa_status(request: Request, db: Session = Depends(get_db)):
    _require_login(request)
    account = db.get(AuthAccount, 1)
    return {'enabled': bool(account and account.mfa_secret)}


@router.post('/mfa/setup')
def mfa_setup(data: PasswordRequest, request: Request, db: Session = Depends(get_db)):
    username = _require_login(request)
    if not os.getenv('APP_AUTH_SECRET') or os.getenv('APP_AUTH_SECRET') == os.getenv('APP_AUTH_PASSWORD'):
        raise HTTPException(503, 'Account security requires a separate server authentication secret.')
    account = _account(db)
    if not _password_matches(data.password, account):
        raise HTTPException(401, 'Current password is incorrect.')
    if account.mfa_secret:
        raise HTTPException(409, 'Authenticator is already enabled.')
    secret = new_totp_secret()
    account.mfa_pending_secret = encrypt_secret(secret)
    db.commit()
    return {'secret': secret, 'uri': totp_uri(username, secret)}


@router.post('/mfa/confirm')
def mfa_confirm(data: MfaConfirmRequest, request: Request, response: Response,
                db: Session = Depends(get_db)):
    username = _require_login(request)
    account = _account(db)
    if account.mfa_secret or not account.mfa_pending_secret:
        raise HTTPException(409, 'Start authenticator setup first.')
    if not verify_totp(decrypt_secret(account.mfa_pending_secret), data.code):
        raise HTTPException(400, 'Authenticator code is incorrect.')
    codes, hashes = new_recovery_codes()
    account.mfa_secret = account.mfa_pending_secret
    account.mfa_pending_secret = None
    account.recovery_code_hashes = hashes
    account.session_version += 1
    db.commit()
    _set_cookie(response, username)
    return {'recovery_codes': codes}
