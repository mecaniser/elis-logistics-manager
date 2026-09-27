"""Payment identities, separate from reconciled balances and monitoring rules."""
import base64
import hashlib
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.models.finance import FinanceEvidence
from app.services import finance as f

VERSION = 'payment-account-v1'


class PaymentAccountInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=80)
    account_type: Literal['card', 'bank', 'cash']
    ownership: Literal['personal', 'business']
    last4: str = Field(default='', pattern=r'^(\d{4})?$')

    @field_validator('name')
    @classmethod
    def trim_name(cls, value):
        if not value.strip(): raise ValueError('Enter an account nickname.')
        return value.strip()


def list_accounts(db, tenant):
    rows = db.query(FinanceEvidence).filter_by(tenant_id=tenant, extraction_version=VERSION).all()
    states = db.query(FinanceEvidence).filter_by(tenant_id=tenant, extraction_version='payment-account-status-v1').all()
    superseded = {r.supersedes_id for r in states}
    removed = {r.extracted['account_id'] for r in states if r.id not in superseded and r.extracted['archived']}
    return sorted([{'id': r.id, **r.extracted} for r in rows if r.id not in removed], key=lambda r: r['name'].casefold())


def get_account(db, tenant, account_id):
    row = db.query(FinanceEvidence).filter_by(id=account_id, tenant_id=tenant, extraction_version=VERSION).first()
    if not row: f.fail('Payment account not found for this business.', 'RESOURCE_NOT_FOUND', 404)
    return {'id': row.id, **row.extracted}


def add_account(db, tenant, request):
    f.lock_business(db, tenant)
    payload = request.model_dump()
    if payload['account_type'] == 'cash' and payload['last4']:
        f.fail('Cash does not have a card or account suffix.')
    rows = db.query(FinanceEvidence).filter_by(tenant_id=tenant, extraction_version=VERSION).all()
    for row in rows:
        existing = {'id': row.id, **row.extracted}
        if all(str(existing[k]).casefold() == str(v).casefold() for k, v in payload.items()):
            set_archived(db, tenant, row.id, False)
            return existing
    content = json.dumps({'kind': VERSION, **payload}, sort_keys=True).encode()
    digest = hashlib.sha256(content).hexdigest()
    row = FinanceEvidence(tenant_id=tenant, sha256=digest, filename='payment-account.json',
        media_type='application/json', content_base64=base64.b64encode(content).decode(),
        source_key=f'payment-account:{digest}', extraction_version=VERSION, extracted=payload)
    db.add(row); db.flush()
    return {'id': row.id, **payload}


def remove_account(db, tenant, account_id):
    f.lock_business(db, tenant)
    get_account(db, tenant, account_id)
    set_archived(db, tenant, account_id, True)
    return {'removed': True, 'id': account_id}


def set_archived(db, tenant, account_id, archived):
    version = 'payment-account-status-v1'
    rows = db.query(FinanceEvidence).filter_by(tenant_id=tenant, extraction_version=version, source_key=f'payment-status:{account_id}').all()
    superseded = {r.supersedes_id for r in rows}
    prior = next((r for r in rows if r.id not in superseded), None)
    if (prior.extracted['archived'] if prior else False) == archived: return
    payload = {'account_id': account_id, 'archived': archived}
    content = json.dumps({**payload, 'previous_id': prior.id if prior else None}, sort_keys=True).encode()
    row = FinanceEvidence(tenant_id=tenant, sha256=hashlib.sha256(content).hexdigest(), filename='payment-account-status.json',
        media_type='application/json', content_base64=base64.b64encode(content).decode(),
        source_key=f'payment-status:{account_id}', extraction_version=version,
        supersedes_id=prior.id if prior else None, extracted=payload)
    db.add(row); db.flush()
