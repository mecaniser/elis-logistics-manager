"""Pure, local financial preview preparation. No database, network or apply path.

Source access/allocation facts must come from trusted server-side reconciliation,
never from untrusted client booleans. Owner-visible historical totals alone do
not authorize their financial export. Production execution is deliberately absent.
"""
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json

ZERO = Decimal('0.00')


@dataclass(frozen=True)
class RecordedPayment:
    amount: Decimal
    paid_on: date
    evidence_ref: str


@dataclass(frozen=True)
class LegacyReplacement:
    repair_id: int
    tenant_id: int
    asset_id: int
    cost: Decimal
    reserve_withdrawn: Decimal = ZERO
    journal_ids: tuple[int, ...] = ()
    confirmed: bool = False


@dataclass(frozen=True)
class InvoiceForPlan:
    tenant_id: int
    shop_id: str
    customer_id: str
    repair_order_id: str
    invoice_id: str
    source_revision: str
    operational_truck_id: int
    cost_asset_id: int | None
    cost_allocation_confirmed: bool
    total: Decimal | None
    service_completed_on: date | None
    invoice_date: date | None  # Evidenced issue date, never an import/creation date.
    financial_access: str
    invoice_state: str = 'current_finalized'
    payments: tuple[RecordedPayment, ...] = ()
    payments_confirmed: bool = False
    replacements: tuple[LegacyReplacement, ...] = ()
    accepted_revision: str | None = None
    existing_cost: Decimal = ZERO
    existing_reserve_withdrawn: Decimal = ZERO


def money(value):
    if not isinstance(value, Decimal) or not value.is_finite() or value < ZERO or value != value.quantize(Decimal('0.01')):
        raise ValueError('Amounts must be finite, nonnegative Decimal cents.')
    return value


def display(value):
    return None if value is None else format(value, '.2f')


def preview_financial_import(*, tenant_id, shop_id, customer_id, invoices,
                             reserve_timing='recorded_payments', reserve_date_basis='payment_date'):
    """Build a reviewable proposal; this function cannot save or grant anything.

    Full invoice cost is an expense, but reserve movement follows only verified
    recorded payment amounts and their actual dates. Occurrence is completion
    date, otherwise an evidenced invoice date; execution remains hard-disabled.
    """
    if reserve_timing != 'recorded_payments':
        raise ValueError('Reserve withdrawals require verified recorded payments only.')
    if reserve_date_basis != 'payment_date':
        raise ValueError('Recorded payments require actual payment dates.')
    global_blockers = []
    rows = []; identities = set(); invoice_ids = set(); replacement_ids = set()
    facts = []
    for item in sorted(invoices, key=lambda i:i.repair_order_id):
        if (item.tenant_id, item.shop_id, item.customer_id) != (tenant_id, shop_id, customer_id):
            raise ValueError('Invoice scope does not match this business connection.')
        if not item.repair_order_id or not item.invoice_id or not item.source_revision:
            raise ValueError('Source identity and revision are required.')
        if item.repair_order_id in identities or item.invoice_id in invoice_ids:
            raise ValueError('Duplicate source identity.')
        identities.add(item.repair_order_id); invoice_ids.add(item.invoice_id)
        blockers = []; schedule = []; replacements = []
        if item.financial_access not in ('authorized_feed', 'owner_review_only', 'unavailable'):
            raise ValueError('Unknown financial access classification.')
        if item.financial_access != 'authorized_feed':
            blockers.append('financial_access_required')
        if not item.cost_asset_id or not item.cost_allocation_confirmed:
            blockers.append('cost_asset_confirmation_required')
        repair_date = item.service_completed_on or item.invoice_date
        if repair_date is None:
            blockers.append('repair_date_evidence_required')
        old_cost = money(item.existing_cost); old_reserve = money(item.existing_reserve_withdrawn)
        for old in sorted(item.replacements,key=lambda r:r.repair_id):
            if old.tenant_id != tenant_id:
                raise ValueError('Replacement scope does not match this business.')
            if old.repair_id in replacement_ids:
                raise ValueError('A replacement repair cannot be used twice.')
            replacement_ids.add(old.repair_id)
            money(old.cost); money(old.reserve_withdrawn)
            if not old.confirmed:
                blockers.append(f'replacement_confirmation_required:{old.repair_id}')
            else:
                old_cost += old.cost; old_reserve += old.reserve_withdrawn
            replacements.append({'repair_id':old.repair_id,'action':'archive_and_link',
                'preserve_evidence':True,'withdrawal_reversal':display(old.reserve_withdrawn),
                'journal_ids_for_correction_review':list(old.journal_ids)})
        paid = ZERO; payment_refs = set()
        for p in item.payments:
            money(p.amount)
            if not p.evidence_ref or not p.paid_on or p.amount == ZERO or p.evidence_ref in payment_refs:
                raise ValueError('Payment requires a unique evidence reference, positive amount and actual date.')
            payment_refs.add(p.evidence_ref); paid += p.amount
        if item.payments and not item.payments_confirmed:
            blockers.append('payment_confirmation_required')
        payment = {'status':'unconfirmed','amount_paid':None,'balance_due':None}
        expense_delta = reserve_delta = target = None
        if item.total is None:
            blockers.append('invoice_total_required')
        else:
            total = money(item.total)
            if paid > total:
                raise ValueError('Recorded payment exceeds the invoice; review overpayment separately.')
            if item.payments_confirmed:
                payment = {'status':'paid' if paid == total else 'partial' if paid else 'unpaid',
                    'amount_paid':display(paid),'balance_due':display(total-paid)}
            expense_delta = total - old_cost
            if item.payments_confirmed or not item.payments:
                target = paid
                schedule = [{'date':p.paid_on.isoformat(),'amount':display(p.amount),'basis':'recorded_payment'}
                            for p in sorted(item.payments,key=lambda p:(p.paid_on,p.evidence_ref))]
                reserve_delta = target - old_reserve
        if item.accepted_revision and item.accepted_revision != item.source_revision:
            blockers.append('invoice_change_review_required')
        if item.invoice_state != 'current_finalized':
            blockers.append('invoice_state_review_required')
            expense_delta = reserve_delta = target = None; schedule = []
        rows.append({'repair_order_id':item.repair_order_id,'invoice_id':item.invoice_id,
            'operational_truck_id':item.operational_truck_id,'cost_asset_id':item.cost_asset_id,
            'invoice_total':display(item.total),'repair_date':repair_date.isoformat() if repair_date else None,
            'payment':payment,'expense_delta':display(expense_delta),'reserve_delta':display(reserve_delta),
            'target_reserve_withdrawal':display(target),'reserve_schedule':schedule,
            'replacement_proposals':replacements,'blockers':blockers})
        facts.append(asdict(item))
    result = {'version':'db094-financial-preview-paid-v1','tenant_id':tenant_id,'shop_id':shop_id,
              'customer_id':customer_id,'reserve_timing':reserve_timing,'reserve_date_basis':reserve_date_basis,
              'blockers':global_blockers,'rows':rows,
              'ready_for_guided_approval':bool(rows) and not global_blockers and not any(r['blockers'] for r in rows),
              'execution_enabled':False}
    canonical = json.dumps({'result':result,'facts':facts},sort_keys=True,separators=(',',':'),default=str)
    result['plan_digest'] = hashlib.sha256(canonical.encode()).hexdigest()
    return result
