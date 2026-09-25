"""Read-only cash planning from a fresh provider balance read.

These figures are ceilings for review, never transfer instructions or proof
that every pending debit has reached the transaction feed.
"""
from app.services.bank_monitor import BalanceSnapshot, MonitorRules


def calculate_cash_plan(rules: MonitorRules, snapshot: BalanceSnapshot, visibility: dict) -> dict:
    balances = {row.last4: row for row in snapshot.accounts}
    reserve = max(rules.buffer_cents, rules.repayment.reserve_cents or 0)
    cash_accounts = []
    remaining = {}
    for configured in rules.checking:
        row = balances.get(configured.last4)
        current = row.current_cents if row else None
        available = row.available_cents if row else None
        # The bank's available balance may already reflect holds. Never subtract
        # observed pending entries from it a second time or count unposted credits.
        conservative = min(current, available) if current is not None and available is not None else None
        spendable = max(0, conservative - reserve) if conservative is not None else None
        remaining[configured.last4] = spendable or 0
        pending_debits = visibility.get('pending_debit_cents', {}).get(configured.last4)
        cash_accounts.append({
            'last4': configured.last4, 'nickname': configured.nickname,
            'current_cents': current, 'available_cents': available,
            'availability_difference_cents': max(0, current - available) if current is not None and available is not None else None,
            'planning_limit_cents': spendable,
            'observed_pending_debit_cents': pending_debits,
            'observed_pending_credit_cents': visibility.get('pending_credit_cents', {}).get(configured.last4),
            'observed_pending_count': visibility.get('pending_debit_entries', {}).get(configured.last4),
            'pending_details': visibility.get('pending_details', {}).get(configured.last4, []),
            'pending_details_truncated': visibility.get('pending_details_truncated', {}).get(configured.last4, False),
        })

    checking_routes = []
    for destination in cash_accounts:
        current, available = destination['current_cents'], destination['available_cents']
        if current is None or available is None:
            continue
        shortfall = max(0, reserve - min(current, available))
        for source in cash_accounts:
            if source['last4'] == destination['last4'] or not shortfall:
                continue
            amount = min(shortfall, remaining[source['last4']])
            if amount:
                checking_routes.append({'from_last4': source['last4'],
                                        'to_last4': destination['last4'], 'amount_cents': amount})
                remaining[source['last4']] -= amount
                shortfall -= amount

    credit_routes = []
    priority = rules.repayment.priority or [row.last4 for row in rules.sources]
    for credit_suffix in priority:
        credit = balances.get(credit_suffix)
        owed = credit.outstanding_cents if credit else None
        if owed is None or owed <= 0:
            continue
        for source in cash_accounts:
            amount = min(owed, remaining[source['last4']])
            if amount:
                credit_routes.append({'from_last4': source['last4'], 'to_last4': credit_suffix,
                                      'amount_cents': amount, 'payoff_unverified': True})
                remaining[source['last4']] -= amount
                owed -= amount
            if not owed:
                break

    return {'observed_at': snapshot.observed_at.isoformat(),
            'reserve_cents': reserve,
            'cash_accounts': cash_accounts,
            'checking_routes': checking_routes,
            'credit_routes': credit_routes,
            'pending_complete': False,
            'transaction_feed_status': visibility.get('status', 'unavailable'),
            'last_transaction_update': visibility.get('last_successful_update'),
            'transfers_executed': False}
