"""Consented Plaid bank reads. No bank password or transfer API is used here."""
import os
from datetime import datetime, timezone
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


def link_token(tenant_id: int, *, access_token: str | None = None) -> str:
    body = {'client_name': 'ELIS Bank Monitor', 'language': 'en',
            'country_codes': ['US'], 'user': {'client_user_id': f'elis-bank-{tenant_id}'}}
    if access_token:
        body['access_token'] = access_token
    else:
        body['products'] = ['transactions']
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
                     now: datetime | None = None) -> BalanceSnapshot:
    observed_at = now or datetime.now(timezone.utc)
    accounts = real_time_accounts(access_token)
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
            if current is None:
                raise PlaidBankError('provider_balance_incomplete')
            values.append(AccountBalance(last4=configured_account.last4,
                                         current_cents=current, available_cents=available))
        else:
            if available is None or available < 0:
                raise PlaidBankError('provider_credit_incomplete')
            values.append(AccountBalance(last4=configured_account.last4,
                                         available_credit_cents=available,
                                         outstanding_cents=current if current is not None and current >= 0 else None))
    return BalanceSnapshot(observed_at=observed_at, accounts=values)
