"""Explicit, fail-closed authorization for access to stored business bank details."""
import os

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth_utils import SESSION_COOKIE_NAME, verify_session_token
from app.database import get_db
from app.models.tenant import Tenant

PRIVATE_HEADERS = {'Cache-Control': 'private, no-store'}


def authorized_bank_tenant(tenant_id: int, request: Request, db: Session = Depends(get_db)) -> Tenant:
    # Deliberately has no unauthenticated local-development bypass.
    expected = os.getenv('APP_AUTH_USERNAME')
    try:
        valid, username = verify_session_token(request.cookies.get(SESSION_COOKIE_NAME, ''))
    except (ValueError, TypeError, AttributeError):
        valid, username = False, None
    if not expected or not valid or username != expected:
        raise HTTPException(401, 'Sign in to access bank details.', headers=PRIVATE_HEADERS)

    allowed = {part.strip() for part in os.getenv('APP_AUTH_TENANT_IDS', '').split(',')}
    if str(tenant_id) not in allowed:
        raise HTTPException(404, 'Business unavailable.', headers=PRIVATE_HEADERS)
    tenant = db.query(Tenant).filter_by(id=tenant_id, is_active=True).first()
    if not tenant:
        raise HTTPException(404, 'Business unavailable.', headers=PRIVATE_HEADERS)
    return tenant
