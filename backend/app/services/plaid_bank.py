"""Consented Plaid bank reads. No bank password or transfer API is used here."""
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx
from cryptography.fernet import Fernet, InvalidToken

from app.services.bank_monitor import AccountBalance, BalanceSnapshot, MonitorRules

TRULIANT_INSTITUTION_ID = 'ins_109917'
HOSTS = {
    'sandbox': 'https://sandbox.plaid.com',
    'development': 'https://development.plaid.com',
    'production': 'https://production.plaid.com',
}


class PlaidBankError(Exception):
    """A safe status code; provider response bodies and credentials are never logged."""


def configured():
    return bool(os.getenv('PLAID_CLIENT_ID') and os.getenv('PLAID_SECRET')
                and os.getenv('BANK_MONITOR_TOKEN_KEY') and os.getenv('PLAID_ENV') in HOSTS
                and os.getenv('PLAID_REDIRECT_URI', '').startswith('https://'))


def environment():
    value = os.getenv('PLAID_ENV', '')
    if value not in HOSTS:
        raise PlaidBankError('provider_not_configured')
    return value


def encrypt_token(token: str) -> str:
    try:
        return Fernet(os.environ['BANK_MONITOR_TOKEN_KEY'].encode()).encrypt(token.encode()).decode()
    except (KeyError, ValueError) as exc:
        raise PlaidBankError('provider_not_configured') from exc


def decrypt_token(value: str) -> str:
    try:
        return Fernet(os.environ['BANK_MONITOR_TOKEN_KEY'].encode()).decrypt(value.encode()).decode()
    except (KeyError, ValueError, InvalidToken) as exc:
        raise PlaidBankError('provider_key_unavailable') from exc


def request(endpoint: str, payload: dict) -> dict:
    if not configured():
        raise PlaidBankError('provider_not_configured')
    body = {**payload, 'client_id': os.environ['PLAID_CLIENT_ID'],
            'secret': os.environ['PLAID_SECRET']}
    try:
        response = httpx.post(HOSTS[environment()] + endpoint, json=body,
                              headers={'Plaid-Version': '2020-09-14'}, timeout=35,
                              follow_redirects=False)
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise PlaidBankError('provider_unavailable') from exc
    if response.is_error:
        code = data.get('error_code') if isinstance(data, dict) else None
        if code in {'ITEM_LOGIN_REQUIRED', 'INVALID_CREDENTIALS', 'ITEM_NOT_SUPPORTED'}:
            raise PlaidBankError('provider_reauthorization_required')
        if code in {'PRODUCT_NOT_READY', 'PRODUCTS_NOT_SUPPORTED'}:
            raise PlaidBankError('provider_data_unavailable')
        raise PlaidBankError('provider_request_failed')
    if not isinstance(data, dict):
        raise PlaidBankError('provider_invalid_response')
    return data


def link_token(tenant_id: int, *, access_token: str | None = None, optional_liabilities: bool = False) -> str:
    body = {'client_name': 'ELIS Bank Monitor', 'language': 'en',
            'country_codes': ['US'], 'user': {'client_user_id': f'elis-bank-{tenant_id}'}}
    if access_token:
        body['access_token'] = access_token
    else:
        body['products'] = ['transactions'] if optional_liabilities else ['transactions', 'liabilities']
        if optional_liabilities:
            body['optional_products'] = ['liabilities']
    body['redirect_uri'] = os.environ['PLAID_REDIRECT_URI']
    token = request('/link/token/create', body).get('link_token')
    if not isinstance(token, str) or not token:
        raise PlaidBankError('provider_invalid_response')
    return token


def exchange(public_token: str) -> tuple[str, str]:
    result = request('/item/public_token/exchange', {'public_token': public_token})
    access_token, item_id = result.get('access_token'), result.get('item_id')
    if not isinstance(access_token, str) or not isinstance(item_id, str):
        raise PlaidBankError('provider_invalid_response')
    return access_token, item_id


def item(access_token: str) -> dict:
    data = request('/item/get', {'access_token': access_token})
    item_data = data.get('item')
    if not isinstance(item_data, dict):
        raise PlaidBankError('provider_invalid_response')
    if item_data.get('error'):
        raise PlaidBankError('provider_reauthorization_required')
    return item_data


def cents(value) -> int | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value)) * 100
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PlaidBankError('provider_invalid_response') from exc
    if not amount.is_finite() or amount != amount.to_integral_value() or abs(amount) > 10000000000:
        raise PlaidBankError('provider_invalid_response')
    return int(amount)


def real_time_accounts(access_token: str) -> list[dict]:
    accounts = request('/accounts/balance/get', {'access_token': access_token}).get('accounts')
    if not isinstance(accounts, list):
        raise PlaidBankError('provider_invalid_response')
    return accounts


def discover_accounts(access_token: str) -> list[dict]:
    """List consented account labels without requesting another paid balance read."""
    accounts = request('/accounts/get', {'access_token': access_token}).get('accounts')
    if not isinstance(accounts, list):
        raise PlaidBankError('provider_invalid_response')
    discovered = []
    for row in accounts:
        kind = ('checking' if row.get('type') == 'depository' and row.get('subtype') == 'checking'
                else 'credit' if row.get('type') in {'credit', 'loan'} else None)
        mask = row.get('mask')
        if kind and isinstance(mask, str) and len(mask) == 4 and mask.isdigit():
            discovered.append({'nickname': str(row.get('name') or row.get('official_name') or kind)[:80],
                               'last4': mask, 'kind': kind})
    return discovered


def synced_transactions(access_token: str, account_map: dict) -> tuple[dict, str | None]:
    """Apply all sync pages, including pending-to-posted removals."""
    ids = {entry['account_id'] for entry in account_map.values()}
    active = {}
    cursor = None
    update_status = None
    for _ in range(50):
        payload = {'access_token': access_token, 'count': 500}
        if cursor:
            payload['cursor'] = cursor
        data = request('/transactions/sync', payload)
        update_status = data.get('transactions_update_status', update_status)
        for row in data.get('added', []) + data.get('modified', []):
            if row.get('account_id') in ids and isinstance(row.get('transaction_id'), str):
                active[row['transaction_id']] = row
        for row in data.get('removed', []):
            active.pop(row.get('transaction_id'), None)
        cursor = data.get('next_cursor')
        if not data.get('has_more'):
            break
    else:
        raise PlaidBankError('provider_history_incomplete')
    if not isinstance(cursor, str):
        raise PlaidBankError('provider_history_incomplete')
    return active, update_status


def transaction_visibility(access_token: str, account_map: dict) -> dict:
    """Report what Plaid supplied, without treating an empty pending feed as complete."""
    item_data = request('/item/get', {'access_token': access_token})
    status = item_data.get('status', {}).get('transactions', {})
    ids = {entry['account_id']: suffix for suffix, entry in account_map.items()}
    active, update_status = synced_transactions(access_token, account_map)
    pending = {suffix: 0 for suffix in account_map}
    posted = {suffix: 0 for suffix in account_map}
    pending_debit_cents = {suffix: 0 for suffix in account_map}
    pending_debit_entries = {suffix: 0 for suffix in account_map}
    pending_credit_cents = {suffix: 0 for suffix in account_map}
    pending_details = {suffix: [] for suffix in account_map}
    for row in active.values():
        suffix = ids[row['account_id']]
        (pending if row.get('pending') is True else posted)[suffix] += 1
        if row.get('pending') is True:
            amount = cents(row.get('amount'))
            if amount is None:
                continue
            if amount > 0:
                pending_debit_cents[suffix] += amount
                pending_debit_entries[suffix] += 1
            elif amount < 0:
                pending_credit_cents[suffix] += -amount
            pending_details[suffix].append({
                'description': str(row.get('merchant_name') or row.get('name') or 'Pending transaction')[:120],
                'amount_cents': amount,
                'date': row.get('authorized_date') or row.get('date'),
            })
    for suffix, details in pending_details.items():
        details.sort(key=lambda row: row['date'] or '', reverse=True)
        pending_details[suffix] = details[:30]
    return {'pending_entries': pending, 'posted_entries': posted,
            'pending_debit_cents': pending_debit_cents,
            'pending_debit_entries': pending_debit_entries,
            'pending_credit_cents': pending_credit_cents,
            'pending_details': pending_details,
            'pending_details_truncated': {suffix: pending[suffix] > 30 for suffix in account_map},
            'transactions_update_status': update_status,
            'last_successful_update': status.get('last_successful_update'),
            'pending_complete': False}


def transfer_match(access_token: str, account_map: dict, *, from_last4: str,
                   to_last4: str, amount_cents: int, earliest: date, memo: str | None = None) -> dict:
    """Find one exact posted debit and credit, never infer completion from one side."""
    source = account_map.get(from_last4)
    destination = account_map.get(to_last4)
    if not source or not destination or source['account_id'] == destination['account_id']:
        raise PlaidBankError('provider_account_mapping_required')
    active, update_status = synced_transactions(access_token, account_map)
    if update_status == 'NOT_READY':
        return {'status': 'feed_not_ready'}
    latest = datetime.now(timezone.utc).date() + timedelta(days=1)

    def candidates(account_id: str, expected: int) -> tuple[list[dict], int]:
        posted, pending = [], 0
        for row in active.values():
            if row.get('account_id') != account_id or cents(row.get('amount')) != expected:
                continue
            try:
                bank_date = date.fromisoformat(row.get('date', ''))
            except (TypeError, ValueError):
                continue
            if bank_date < earliest or bank_date > latest:
                continue
            if row.get('pending') is True:
                pending += 1
                continue
            posted.append({'transaction_id': row['transaction_id'],
                           'description': str(row.get('name') or row.get('merchant_name') or '')[:120],
                           'date': bank_date.isoformat(), 'amount_cents': expected})
        return posted, pending

    debits, pending_debits = candidates(source['account_id'], amount_cents)
    credits, pending_credits = candidates(destination['account_id'], -amount_cents)
    if not debits or not credits:
        return {'status': 'posting_pending' if pending_debits or pending_credits or debits or credits else 'not_found',
                'source_posted': len(debits), 'destination_posted': len(credits)}
    if len(debits) != 1 or len(credits) != 1:
        return {'status': 'ambiguous', 'source_posted': len(debits), 'destination_posted': len(credits)}
    debit, credit = debits[0], credits[0]
    if abs((date.fromisoformat(debit['date']) - date.fromisoformat(credit['date'])).days) > 3:
        return {'status': 'ambiguous', 'source_posted': 1, 'destination_posted': 1}
    descriptions = f"{debit['description']} {credit['description']}".lower()
    if not re.search(r'\b(transfer|xfer|payment|pymt|payoff)\b', descriptions):
        return {'status': 'needs_bank_review', 'source_posted': 1, 'destination_posted': 1}
    normalize = lambda value: re.sub(r'\s+', ' ', value).strip().casefold()
    # Amount/date agreement alone is insufficient for unattended reconciliation.
    # Require the draft's distinct reference on BOTH posted entries.
    reference_matched = bool(memo and all(re.search(r'(?<![\w-])' + re.escape(normalize(memo)) + r'(?![\w-])', normalize(row['description'])) for row in (debit, credit)))
    return {'status': 'ready_for_confirmation', 'source': debit, 'destination': credit,
            'reference_matched': reference_matched}


def map_accounts(accounts: list[dict], rules: MonitorRules) -> dict:
    """Bind every configured suffix to one exact, typed provider account."""
    mapping = {}
    for expected, kind in [(account, 'checking') for account in rules.checking] + [
            (account, 'credit') for account in rules.sources]:
        matches = [row for row in accounts if row.get('mask') == expected.last4 and
                   ((row.get('type') == 'depository' and row.get('subtype') == 'checking')
                    if kind == 'checking' else row.get('type') in {'credit', 'loan'})]
        if len(matches) != 1 or not isinstance(matches[0].get('account_id'), str):
            raise PlaidBankError('provider_account_mapping_required')
        mapping[expected.last4] = {'account_id': matches[0]['account_id'], 'kind': kind}
    if len({entry['account_id'] for entry in mapping.values()}) != len(mapping):
        raise PlaidBankError('provider_account_mapping_required')
    return mapping


def balance_snapshot(access_token: str, rules: MonitorRules, account_map: dict,
                     now: datetime | None = None, rows: list[dict] | None = None) -> BalanceSnapshot:
    observed_at = now or datetime.now(timezone.utc)
    accounts = rows if rows is not None else real_time_accounts(access_token)
    rows_by_id = {row.get('account_id'): row for row in accounts}
    values = []
    for configured_account in rules.checking + rules.sources:
        mapping = account_map.get(configured_account.last4)
        if not isinstance(mapping, dict):
            raise PlaidBankError('provider_account_mapping_required')
        row = rows_by_id.get(mapping.get('account_id'))
        if not isinstance(row, dict) or row.get('mask') != configured_account.last4:
            raise PlaidBankError('provider_account_mapping_required')
        expected_kind = 'checking' if configured_account in rules.checking else 'credit'
        if mapping.get('kind') != expected_kind:
            raise PlaidBankError('provider_account_mapping_required')
        if expected_kind == 'checking' and (row.get('type'), row.get('subtype')) != ('depository', 'checking'):
            raise PlaidBankError('provider_account_mapping_required')
        if expected_kind == 'credit' and row.get('type') not in {'credit', 'loan'}:
            raise PlaidBankError('provider_account_mapping_required')
        balances = row.get('balances')
        if not isinstance(balances, dict) or balances.get('iso_currency_code') != 'USD':
            raise PlaidBankError('provider_invalid_response')
        current = cents(balances.get('current'))
        available = cents(balances.get('available'))
        if expected_kind == 'checking':
            values.append(AccountBalance(last4=configured_account.last4,
                                         current_cents=current, available_cents=available))
        else:
            if available is not None and available < 0:
                raise PlaidBankError('provider_credit_incomplete')
            values.append(AccountBalance(last4=configured_account.last4,
                                         available_credit_cents=available,
                                         outstanding_cents=current if current is not None and current >= 0 else None))
    return BalanceSnapshot(observed_at=observed_at, accounts=values)
