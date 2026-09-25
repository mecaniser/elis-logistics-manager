"""Server-derived accounting authority. A header selects; it never grants access."""
import os
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth_utils import verify_session_token, SESSION_COOKIE_NAME
from app.models.tenant import Tenant


def accounting_tenant(request: Request, db: Session = Depends(get_db)) -> int:
    username = os.getenv('APP_AUTH_USERNAME')
    valid, principal = verify_session_token(request.cookies.get(SESSION_COOKIE_NAME, ''))
    local_ids = os.getenv('ELIS_FINANCE_LOCAL_TENANTS', '')
    local = not username and local_ids and request.client and request.client.host in ('127.0.0.1', '::1', 'testclient')
    if not local and not (valid and username and principal == username):
        raise HTTPException(401, detail={'code': 'AUTHENTICATION_REQUIRED', 'message': 'Sign in to access accounting.'})
    selectors = request.headers.getlist('x-tenant-id')
    if not selectors:
        raise HTTPException(400, detail={'code': 'TENANT_CONTEXT_REQUIRED', 'message': 'X-Tenant-ID is required.'})
    if len(selectors) != 1 or not selectors[0].isascii() or not selectors[0].isdigit() or int(selectors[0]) <= 0:
        raise HTTPException(400, detail={'code': 'TENANT_CONTEXT_INVALID', 'message': 'Provide exactly one positive tenant selector.'})
    selected = int(selectors[0])
    allowlist = local_ids if local else os.getenv('APP_AUTH_TENANT_IDS', '')
    allowed = {int(x.strip()) for x in allowlist.split(',') if x.strip().isdigit()}
    if selected not in allowed or not db.query(Tenant).filter_by(id=selected, is_active=True).first():
        raise HTTPException(404, detail={'code': 'RESOURCE_NOT_FOUND', 'message': 'Resource not found.'})
    if 'tenant_id' in request.query_params or 'tenant_id' in request.path_params:
        raise HTTPException(400, detail={'code': 'TENANT_CONTEXT_INVALID', 'message': 'Business scope is selected only by the authorized header.'})
    return selected
