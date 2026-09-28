"""Read-only Dashboard usage; never refreshes bank accounts or logs credentials."""
import json
import os
import threading
import time
from datetime import datetime, timezone
import httpx

_lock = threading.Lock()
_cache = None
_cache_key = None
_expires = 0
METRICS = ['balance-request', 'transactions', 'transactions-active', 'transactions-refresh',
           'liabilities', 'liabilities-active', 'identity-request', 'auth-request']


def _rpc(client, token, name, arguments):
    response = client.post('https://api.dashboard.plaid.com/mcp/',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json, text/event-stream'},
        json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
              'params': {'name': name, 'arguments': arguments}})
    response.raise_for_status()
    if 'text/event-stream' in response.headers.get('content-type', ''):
        messages = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        data = next(message for message in messages if message.get('id') == 1)
    else:
        data = response.json()
    result = data['result']
    if result.get('isError'):
        raise ValueError('dashboard_error')
    return json.loads(next(block['text'] for block in result['content'] if block.get('type') == 'text'))


def usage():
    global _cache, _cache_key, _expires
    team = os.getenv('PLAID_DASHBOARD_TEAM_ID')
    if os.getenv('PLAID_ENV') != 'production' or not team:
        return {'status': 'not_connected', 'metrics': []}
    now = datetime.now(timezone.utc)
    start = now.strftime('%Y-%m-01')
    key = (team, os.getenv('PLAID_CLIENT_ID'), start)
    with _lock:
        if _cache_key == key and time.monotonic() < _expires:
            return _cache
        try:
            with httpx.Client(timeout=15, follow_redirects=False) as client:
                response = client.post('https://production.plaid.com/oauth/token', json={
                    'client_id': os.environ['PLAID_CLIENT_ID'], 'client_secret': os.environ['PLAID_SECRET'],
                    'grant_type': 'client_credentials', 'scope': 'mcp:dashboard'})
                response.raise_for_status()
                data = _rpc(client, response.json()['access_token'], 'plaid_get_usages', {
                    'team_id': team, 'period_start': start, 'period_end': now.strftime('%Y-%m-%d'),
                    'metric_types': METRICS})
            # Preserve provider series; empty observations are unavailable, never a zero bill.
            metrics = [{'metric': row['metricName'], 'observations': row.get('totalObservations', 0),
                        'series': row.get('series', []), 'start': row.get('start'), 'end': row.get('end')}
                       for row in data['series'] if row.get('metricName') in METRICS]
            _cache = {'status': 'available', 'checked_at': now.isoformat(), 'period_start': start,
                      'period_end': now.strftime('%Y-%m-%d'), 'metrics': metrics}
            _expires = time.monotonic() + 3600
        except Exception:
            # Return no provider error body: it can contain account identifiers.
            previous = _cache if _cache_key == key else None
            _cache = {**(previous or {'metrics': []}), 'status': 'unavailable'}
            _expires = time.monotonic() + 60
        _cache_key = key
        return _cache
