"""Explicit identity links. Observed balances never establish reconciled cash."""
import base64
import json
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.models.finance import FinanceEvidence
from app.models.bank_monitor import BankMonitorConfig, BankMonitorRun
from app.services import finance as f
from app.services.payment_accounts import get_account

VERSION = 'payment-account-link-v1'


class AccountLinkInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['ledger', 'monitor']
    source_id: str = Field(min_length=1, max_length=80)
    previous_id: str | None = None


def sources(db, tenant, monitor_allowed=False):
    state = f.state(db, tenant, date.today())
    result = []
    for id, account in state['accounts'].items():
        statements = [s for s in state['statements'].values() if s['account_id'] == id]
        latest = max(statements, key=lambda s: s['end'], default=None)
        result.append({'id': id, 'provider': 'ledger', 'name': account['name'], 'account_type': account['account_type'],
                       'balance': latest['closing'] if latest else None, 'as_of': latest['end'] if latest else None,
                       'basis': 'reconciled_statement' if latest else 'no_statement', 'source_ref': latest['id'] if latest else id})
    if monitor_allowed:
        config = db.get(BankMonitorConfig, tenant)
        runs = db.query(BankMonitorRun).filter_by(tenant_id=tenant).order_by(BankMonitorRun.started_at.desc()).all()
        for group in ('checking', 'sources'):
            for a in (config.rules if config else {}).get(group, []):
                kind = 'bank' if group == 'checking' else 'card' if a.get('kind') == 'credit' else None
                if not kind: continue
                balance = None; observed = None; run_id = None
                for run in runs:
                    r = run.result or {}
                    rows = r.get('accounts', []) if kind == 'bank' else r.get('credit_accounts', [])
                    matches = [x for x in rows if x.get('last4') == a['last4']]
                    if len(matches) == 1 and r.get('observed_at'):
                        amount = matches[0].get('current_cents' if kind == 'bank' else 'outstanding_cents')
                        balance = f.money(f.D(amount) / 100) if amount is not None else None
                        observed = r['observed_at']; run_id = str(run.id); break
                result.append({'id': f"{group}:{a['last4']}", 'provider': 'monitor', 'name': a['nickname'], 'last4': a['last4'], 'account_type': kind,
                               'balance': balance, 'as_of': observed, 'basis': 'observed_not_reconciled', 'source_ref': run_id})
    return result


def current_link(db, tenant, account_id, provider):
    rows = db.query(FinanceEvidence).filter_by(tenant_id=tenant, extraction_version=VERSION, source_key=f'payment-link:{account_id}:{provider}').all()
    superseded = {r.supersedes_id for r in rows}
    return next((r for r in rows if r.id not in superseded), None)


def link_account(db, tenant, account_id, request, monitor_allowed=False):
    f.lock_business(db, tenant)
    account = get_account(db, tenant, account_id)
    if request.provider == 'monitor' and not monitor_allowed: f.fail('Sign in to Bank Monitor before connecting a monitored account.', status=403)
    candidates = [s for s in sources(db, tenant, monitor_allowed) if s['provider'] == request.provider and s['id'] == request.source_id]
    if len(candidates) != 1: f.fail('Balance source unavailable or ambiguous.', 'RESOURCE_NOT_FOUND', 404)
    source = candidates[0]
    if source['account_type'] != account['account_type']: f.fail('Choose the same account type.')
    if request.provider == 'ledger' and account['ownership'] != 'business': f.fail('Personal accounts must not enter the business cash ledger.')
    # Prevent one balance appearing under two distinct payment identities.
    others = db.query(FinanceEvidence).filter_by(tenant_id=tenant, extraction_version=VERSION).all()
    superseded = {r.supersedes_id for r in others}
    for r in others:
        if r.id not in superseded and r.extracted['provider'] == request.provider and r.extracted['source_id'] == request.source_id and r.extracted['account_id'] != account_id:
            f.fail('This balance source is already linked to another payment account.')
    prior = current_link(db, tenant, account_id, request.provider)
    identity = {k: source.get(k) for k in ('id', 'provider', 'name', 'account_type', 'last4')}
    payload = {'account_id': account_id, 'provider': request.provider, 'source_id': request.source_id, 'identity': identity}
    if prior and prior.extracted == payload: return {'id': prior.id, **payload}
    if (prior.id if prior else None) != request.previous_id: f.fail('The account link changed. Refresh before replacing it.', 'STALE_LINK')
    content = json.dumps({**payload, 'previous_id': request.previous_id}, sort_keys=True).encode()
    row = FinanceEvidence(tenant_id=tenant, sha256=f.digest(content.decode()), filename='payment-account-link.json', media_type='application/json',
        source_key=f'payment-link:{account_id}:{request.provider}', supersedes_id=request.previous_id,
        content_base64=base64.b64encode(content).decode(), extraction_version=VERSION, extracted=payload)
    db.add(row); db.flush()
    return {'id': row.id, **payload}


def account_balances(db, tenant, account_id, monitor_allowed=False):
    get_account(db, tenant, account_id)
    available = sources(db, tenant, monitor_allowed)
    result = []
    for provider in ('ledger', 'monitor'):
        link = current_link(db, tenant, account_id, provider)
        if not link: continue
        source = next((s for s in available if s['provider'] == provider and s['id'] == link.extracted['source_id']), None)
        identity = {k: source.get(k) for k in ('id', 'provider', 'name', 'account_type', 'last4')} if source else None
        valid = identity == link.extracted['identity']
        result.append({'link_id': link.id, 'provider': provider, 'status': 'linked' if valid else 'review_required',
                       'source': source if valid else None, 'reason': '' if valid else 'Source changed or access is unavailable. Review the link.'})
    return result
