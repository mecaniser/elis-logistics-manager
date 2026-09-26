"""Bank-reported transfer estimates. No transfer submission or payoff assurance."""
from app.services.bank_monitor import BalanceSnapshot, MonitorRules


def build_review(rules: MonitorRules, snapshot: BalanceSnapshot, visibility: dict, drafts) -> dict:
    balances = {a.last4: a for a in snapshot.accounts}
    reserve = max(rules.buffer_cents, rules.repayment.reserve_cents or 0)
    outgoing, incoming = {}, {}
    for draft in drafts:
        if draft.status == 'bank_history_matched':
            continue
        outgoing[draft.from_last4] = outgoing.get(draft.from_last4, 0) + draft.amount_cents
        incoming[draft.to_last4] = incoming.get(draft.to_last4, 0) + draft.amount_cents
    cash, credit, issues = [], [], []
    for account in rules.checking:
        balance = balances.get(account.last4)
        current = balance.current_cents if balance else None
        available = balance.available_cents if balance else None
        pending = visibility.get('pending_debit_cents', {}).get(account.last4)
        held = outgoing.get(account.last4, 0)
        # Compare independent limits; do not subtract pending from available,
        # which may already include those holds. Never count pending credits.
        base = min(current, available, current - (pending or 0)) if current is not None and available is not None else None
        limit = max(0, base - reserve - held) if base is not None else None
        if base is None:
            issues.append(f'Current or available balance is missing for {account.nickname} · ••{account.last4}. Refresh the bank connection.')
        cash.append({**account.model_dump(), 'current_cents': current, 'available_cents': available,
                     'reported_pending_cents': pending, 'queued_cents': held, 'reserve_cents': reserve,
                     'limit_cents': limit, 'shortfall_cents': max(0, reserve - base) if base is not None else None})
    for suffix in rules.repayment.priority:
        account = next(a for a in rules.sources if a.last4 == suffix)
        balance = balances.get(suffix)
        owed = balance.outstanding_cents if balance else None
        credit.append({**account.model_dump(), 'owed_cents': owed,
                       'remaining_cents': max(0, owed - incoming.get(suffix, 0)) if owed is not None else None})
    routes = []
    remaining = {a['last4']: a['limit_cents'] or 0 for a in cash}
    has_shortfall = any(a['shortfall_cents'] for a in cash)
    if not issues:
        if has_shortfall:
            for destination in cash:
                needed = max(0, (destination['shortfall_cents'] or 0) - incoming.get(destination['last4'], 0))
                for source in cash:
                    if source['last4'] == destination['last4']:
                        continue
                    amount = min(needed, remaining[source['last4']])
                    if amount > 0:
                        routes.append({'kind': 'checking', 'from_last4': source['last4'], 'to_last4': destination['last4'], 'amount_cents': amount})
                        remaining[source['last4']] -= amount
                        needed -= amount
            issues.append('Checking needs coverage first. Credit repayments become available after coverage posts and balances refresh.')
        else:
            for destination in credit:
                owed = destination['remaining_cents']
                if owed is None:
                    issues.append(f'Balance owed is missing for {destination["nickname"]} · ••{destination["last4"]}. Later repayment priorities are paused.')
                    break
                for source in cash:
                    amount = min(owed, remaining[source['last4']])
                    if amount > 0:
                        routes.append({'kind': 'repayment', 'from_last4': source['last4'], 'to_last4': destination['last4'], 'amount_cents': amount})
                        remaining[source['last4']] -= amount
                        owed -= amount
    return {'source': 'plaid_review', 'observed_at': snapshot.observed_at.isoformat(),
            'cash_accounts': cash, 'credit_accounts': credit, 'proposals': routes, 'issues': issues,
            'pending_complete': False, 'transaction_feed_status': visibility.get('status', 'unavailable'),
            'last_transaction_update': visibility.get('last_successful_update'), 'transfers_executed': False}
