"""Evidence-backed equipment payment register, separate from forecast allocations.

Consumes an imported bank debit once. It is a management cash-flow record, not
an acquisition journal or a new expense/owner claim. Formal books remain separate.
"""
from datetime import date
from app.models.truck import Truck
from app.services.finance import D, ZERO, money, fail, resource, state
from app.services.trailer_investment import plan_for_day
from app.schemas.investment import InvestmentPlan


def payment_events(s, asset_id=None):
    return [e for e in s['events'] if e.kind == 'equipment_payment'
            and e.id in s['active_event_ids']
            and (asset_id is None or e.payload['asset_id'] == asset_id)]


def validate_command(db, tenant, p, when, s, all_state):
    if when > date.today():
        fail('Use today or an earlier date for a payment record. A due date may be in the future.')
    if p['kind'] == 'equipment_payment_void':
        original = resource(db, tenant, p['payment_id'], {'equipment_payment'})
        if original.id not in all_state['active_event_ids']:
            fail('This payment has already been removed.')
        if when < original.effective_date:
            fail('A correction cannot precede its payment.')
        # Releasing a bank match must not bypass a closed historical period.
        closed = {}
        for e in all_state['events']:
            if e.kind in ('close_period', 'reopen_period'):
                closed[(e.payload['start'], e.payload['end'])] = e.kind == 'close_period'
        if any(active and start <= original.effective_date.isoformat() <= end for (start, end), active in closed.items()):
            fail('Reopen the payment period before correcting this record.', 'PERIOD_CLOSED')
        return
    asset = db.query(Truck).filter_by(id=p['asset_id'], tenant_id=tenant).one()
    plan = plan_for_day(asset, when)
    if asset.vehicle_type != 'trailer' or not plan or D(plan['financed']) <= 0:
        fail('Save a financed trailer plan before recording its payments.')
    if p['kind'] == 'equipment_payment_due':
        if D(p['amount']) <= 0:
            fail('Enter a positive payment amount.')
        return
    if len({D(x['financed']) for x in asset.investment_plans if x['effective'] <= when.isoformat()}) > 1:
        fail('Reconcile borrowing changes before recording payments against this plan.')
    tx = all_state['transactions'].get(p['transaction_id'])
    if not tx or all_state['accounts'][tx['account_id']]['account_type'] != 'bank':
        fail('Choose a debit from an imported bank statement.')
    if tx['id'] in all_state['matches'] or all_state['allocated'].get(tx['id']):
        fail('This bank transaction is already matched. Correct its existing record first.', 'ALREADY_MATCHED')
    for existing in payment_events(all_state):
        source = all_state['transactions'].get(existing.payload['transaction_id'], {})
        if source.get('evidence_id') == tx['evidence_id'] and source.get('external_id') == tx['external_id']:
            fail('This statement payment was already recorded through another account.', 'ALREADY_MATCHED')
    if tx['date'] != when.isoformat():
        fail('Payment date must match the posted bank transaction date.')
    principal, interest = D(p['principal']), D(p['interest'])
    if principal + interest <= 0 or principal + interest != -D(tx['amount']):
        fail('Principal plus interest must equal the entire dedicated bank payment.')
    paid = sum((D(e.payload['principal']) for e in payment_events(all_state, asset.id)), ZERO)
    if paid + principal > D(plan['financed']):
        fail('Recorded principal would exceed the amount borrowed for this trailer.')


def summary(db, tenant, asset, as_of, s=None):
    s = s or state(db, tenant, as_of)
    rows = payment_events(s, asset.id)
    plan = plan_for_day(asset, as_of)
    if not plan:
        return None
    principal = sum((D(e.payload['principal']) for e in rows), ZERO)
    interest = sum((D(e.payload['interest']) for e in rows), ZERO)
    dues = [e for e in s['events'] if e.kind == 'equipment_payment_due' and e.payload['asset_id'] == asset.id]
    due = max(dues, key=lambda e: e.sequence) if dues else None
    return {'principal_paid': money(principal), 'interest_paid': money(interest),
            'payments_total': money(principal + interest), 'payment_count': len(rows),
            'remaining_from_records': money(D(plan['financed']) - principal),
            'due': {**due.payload, 'id': due.id} if due else None,
            'payments': [{'id': e.id, 'date': e.effective_date.isoformat(), **e.payload,
                          'transaction': s['transactions'].get(e.payload['transaction_id'])} for e in reversed(rows)]}


def workspace(db, tenant, as_of):
    s = state(db, tenant, as_of)
    all_state = state(db, tenant, date.max)
    from app.models.bank_monitor import BankEquipmentAccount
    links = {r.asset_id: r.account_id for r in db.query(BankEquipmentAccount).filter_by(tenant_id=tenant)}
    assets = []
    for a in db.query(Truck).filter_by(tenant_id=tenant, vehicle_type='trailer').all():
        plan = plan_for_day(a, as_of)
        if not plan or D(plan['financed']) <= 0:
            continue
        assets.append({'id': a.id, 'name': a.name, 'vin': a.vin,
                       'bank_account_id': links.get(a.id), 'funding': plan['funding'],
                       'borrowed': plan['financed'], 'facility': plan.get('lender') or plan['funding'].upper(),
                       'monthly_payment': InvestmentPlan.model_validate(plan).projection()['monthly_payment'],
                       **summary(db, tenant, a, as_of, s)})
    txs = [{**t, 'account_name': s['accounts'][t['account_id']]['name']} for t in s['transactions'].values()
           if D(t['amount']) < 0 and s['accounts'][t['account_id']]['account_type'] == 'bank'
           and t['id'] not in all_state['matches'] and not all_state['allocated'].get(t['id'])]
    return {'as_of': as_of.isoformat(), 'assets': assets, 'transactions': sorted(txs, key=lambda t: t['date'], reverse=True)}
