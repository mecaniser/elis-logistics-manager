"""Settlement-based scenarios. Never creates income, payments or reserve events."""
from datetime import date, timedelta
from decimal import Decimal
from app.models.settlement import Settlement
from app.models.truck import Truck
from app.schemas.investment import InvestmentPlan
from app.services.trailer_investment import plan_for_day, plan_end, money, plan_day_targets

D = lambda x: Decimal(str(x or 0))
ZERO = Decimal(0)


def income_sources(db, tenant, asset, start, end):
    # Original truck split wins over its generated trailer copy. Unlinked rental
    # settlements remain separate receipts. Never follow a cross-tenant source.
    rows = db.query(Settlement).join(Truck, Settlement.truck_id == Truck.id).filter(
        Truck.tenant_id == tenant, Settlement.settlement_date >= start,
        Settlement.settlement_date <= end).all()
    originals = {r.id: r for r in rows if r.source_settlement_id is None}
    result = []
    for r in originals.values():
        if r.trailer_income_split_trailer_id == asset.id and r.truck_id != asset.id:
            result.append({'id': r.id, 'date': r.settlement_date, 'amount': D(r.trailer_income_split_amount), 'kind': 'Truck allocation'})
        elif r.truck_id == asset.id:
            result.append({'id': r.id, 'date': r.settlement_date, 'amount': D(r.gross_revenue), 'kind': 'Trailer income'})
    return sorted(result, key=lambda r: (r['date'], r['id']))


def settlement_progress(asset, rows, as_of):
    plans = asset.investment_plans or []
    plan = plan_for_day(asset, as_of)
    if not plan:
        return None
    first = min(p['effective'] for p in plans)
    start = date.fromisoformat(first)
    if len({D(p['financed']) for p in plans if p['effective'] <= as_of.isoformat()}) > 1:
        return {'unavailable': 'Borrowing changed between plan revisions. A dated financing adjustment is needed before projecting historical debt.'}
    current = InvestmentPlan.model_validate(plan).projection()
    balance = D(plans[0]['financed'])
    original = balance
    interest = payments = recovery = allocated = ZERO
    by_day = {}
    sources = []
    recent_payment = ZERO
    recent_start = max(start, as_of - timedelta(days=89))
    day = start
    projections = {p['effective']: InvestmentPlan.model_validate(p).projection() for p in plans}
    for row in rows:
        if start <= row['date'] <= as_of:
            by_day.setdefault(row['date'], []).append(row)
    while day <= as_of:
        active = plan_for_day(asset, day)
        projection = projections[active['effective']]
        # Simple daily interest scenario. Lender timing, rate changes and actual
        # payments can differ; no historical payment is asserted.
        charge = balance * D(active['annual_rate']) / 365
        balance += charge
        interest += charge
        for row in by_day.get(day, []):
            amount = row['amount']
            allocated += amount
            budget = D(active['monthly_allocation'])
            positive = max(amount, ZERO)
            planned_payment = positive * D(projection['monthly_payment']) / budget if budget else ZERO
            payment = D(money(min(planned_payment, max(balance - D(active['balance_at_sale']), ZERO))))
            balance -= payment
            payments += payment
            remaining_recovery = max(D(projection['protected_cash_recovery']) - recovery, ZERO)
            recovered = D(money(min(positive * D(projection['monthly_cash_recovery']) / budget if budget else ZERO, remaining_recovery)))
            recovery += recovered
            if day >= recent_start:
                recent_payment += planned_payment
            sources.append({'id': row['id'], 'date': day.isoformat(), 'kind': row['kind'], 'income': money(amount), 'loan_allocation': money(payment), 'cash_recovery': money(recovered)})
        day += timedelta(days=1)
    target = D(plan['balance_at_sale'])
    daily_payment = recent_payment / max((as_of - recent_start).days + 1, 1)
    projected_date = None
    forecast = balance
    if balance <= target:
        projected_date = as_of.isoformat()
    elif daily_payment > balance * D(plan['annual_rate']) / 365:
        # Bounded extrapolation: no promised date when recent pace cannot cover interest.
        for n in range(1, 365 * 30 + 1):
            forecast += forecast * D(plan['annual_rate']) / 365 - daily_payment
            if forecast <= target:
                projected_date = (as_of + timedelta(days=n)).isoformat()
                break
    week_end = as_of - timedelta(days=as_of.weekday() + 1)
    week_start = week_end - timedelta(days=6)
    weekly_cash = weekly_loan = ZERO
    for offset in range(7):
        target_day = week_start + timedelta(days=offset)
        target_plan = plan_for_day(asset, target_day)
        if target_plan:
            cash_target, loan_target = plan_day_targets(target_plan, target_day)
            weekly_cash += cash_target
            weekly_loan += loan_target
    return {'original_borrowed': money(original), 'initial_cash': current['initial_cash'],
            'cash_recovery_target': current['protected_cash_recovery'], 'sale_equity': current['sale_equity'],
            'week_start': week_start.isoformat(), 'week_end': week_end.isoformat(),
            'weekly_loan_target': money(weekly_loan), 'weekly_cash_target': money(weekly_cash),
            'as_of': as_of.isoformat(), 'start': start.isoformat(), 'source_count': len(sources),
            'allocated_income': money(allocated), 'loan_allocation': money(payments),
            'modeled_interest': money(interest), 'modeled_principal_reduction': money(original - balance),
            'projected_balance': money(balance), 'cash_recovery': money(recovery),
            'cash_recovery_remaining': money(max(D(current['protected_cash_recovery']) - recovery, ZERO)),
            'remaining_after_allocations': money(allocated - payments - recovery),
            'balance_target': money(target), 'target_date': projected_date, 'planned_sale': plan_end(plan).isoformat(),
            'recent_monthly_payment_pace': money(daily_payment * Decimal('365') / 12),
            'actual_balance': None, 'sources': list(reversed(sources)),
            'basis': 'Saved settlement allocations; payments proportional to the monthly plan. Daily interest estimate. Before trailer operating costs; not bank payment evidence.'}


def investment_progress(db, tenant, asset, as_of):
    if not asset.investment_plans:
        return None
    start = date.fromisoformat(min(p['effective'] for p in asset.investment_plans))
    return settlement_progress(asset, income_sources(db, tenant, asset, start, as_of), as_of)
