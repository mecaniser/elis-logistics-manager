"""Local-only preparation: explicit policy and evidence, no financial writes."""
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
import pytest
from app.services.dieselbridge_financial_plan import InvoiceForPlan, LegacyReplacement, RecordedPayment, preview_financial_import


def invoice(**changes):
    return replace(InvoiceForPlan(tenant_id=1, shop_id='shop', customer_id='customer',
        repair_order_id='ro', invoice_id='invoice', source_revision='v1', operational_truck_id=1,
        cost_asset_id=1, cost_allocation_confirmed=True, total=D('1000.00'),
        service_completed_on=date(2026, 4, 20), invoice_date=date(2026, 8, 29),
        financial_access='authorized_feed'), **changes)


def plan(rows=None, timing='recorded_payments'):
    return preview_financial_import(tenant_id=1, shop_id='shop', customer_id='customer',
        invoices=rows or [invoice()], reserve_timing=timing,
        reserve_date_basis='payment_date')


def test_paid_only_policy_is_fixed_without_another_timing_decision():
    result=preview_financial_import(tenant_id=1,shop_id='shop',customer_id='customer',invoices=[invoice()])
    assert result['ready_for_guided_approval']
    assert result['blockers']==[]
    assert result['reserve_timing']=='recorded_payments' and result['reserve_date_basis']=='payment_date'
    assert result['rows'][0]['expense_delta']=='1000.00'
    assert result['rows'][0]['reserve_delta']=='0.00'
    assert result['execution_enabled'] is False


def test_unconfirmed_payment_is_not_inferred_paid_or_unpaid():
    row=plan()['rows'][0]
    assert row['payment']=={'status':'unconfirmed','amount_paid':None,'balance_due':None}
    assert row['repair_date']=='2026-04-20'


def test_partial_payment_shows_paid_and_due():
    p=RecordedPayment(amount=D('200.00'), paid_on=date(2026,5,1), evidence_ref='owner-confirmation')
    row=plan([invoice(payments=(p,), payments_confirmed=True)],'recorded_payments')['rows'][0]
    assert row['payment']=={'status':'partial','amount_paid':'200.00','balance_due':'800.00'}
    assert row['expense_delta']=='1000.00'
    assert row['reserve_delta']=='200.00'
    assert row['reserve_schedule']==[{'date':'2026-05-01','amount':'200.00','basis':'recorded_payment'}]


@pytest.mark.parametrize('timing',[None,'final_invoice','unknown'])
def test_any_other_reserve_timing_is_rejected(timing):
    with pytest.raises(ValueError,match='verified recorded payments'):
        plan(timing=timing)


def test_evidenced_invoice_date_is_fallback_not_creation_date():
    assert plan([invoice(service_completed_on=None)])['rows'][0]['repair_date']=='2026-08-29'
    result=plan([invoice(service_completed_on=None,invoice_date=None)])
    assert 'repair_date_evidence_required' in result['rows'][0]['blockers']


def test_owner_visible_total_does_not_authorize_export():
    result=plan([invoice(financial_access='owner_review_only')])
    assert result['rows'][0]['invoice_total']=='1000.00'
    assert 'financial_access_required' in result['rows'][0]['blockers']
    assert not result['ready_for_guided_approval']


def test_replacement_is_explicit_reversible_and_nets_existing_effects():
    old=LegacyReplacement(repair_id=136,tenant_id=1,asset_id=1,cost=D('150.00'),
        reserve_withdrawn=D('150.00'),journal_ids=(9,),confirmed=True)
    row=plan([invoice(replacements=(old,))])['rows'][0]
    assert row['expense_delta']=='850.00' and row['reserve_delta']=='-150.00'
    assert row['replacement_proposals']==[{'repair_id':136,'action':'archive_and_link',
        'preserve_evidence':True,'withdrawal_reversal':'150.00','journal_ids_for_correction_review':[9]}]


def test_unconfirmed_replacement_or_asset_is_blocked():
    old=LegacyReplacement(repair_id=136,tenant_id=1,asset_id=1,cost=D('150.00'))
    row=plan([invoice(replacements=(old,),cost_allocation_confirmed=False)])['rows'][0]
    assert 'replacement_confirmation_required:136' in row['blockers']
    assert 'cost_asset_confirmation_required' in row['blockers']


def test_replay_has_zero_cost_and_reserve_delta_and_stable_digest():
    source=invoice(existing_cost=D('1000.00'),existing_reserve_withdrawn=D('1000.00'),accepted_revision='v1',payments=(RecordedPayment(D('1000.00'),date(2026,5,1),'verified'),),payments_confirmed=True)
    a=plan([source]);b=plan([source])
    assert a['rows'][0]['expense_delta']=='0.00' and a['rows'][0]['reserve_delta']=='0.00'
    assert a['plan_digest']==b['plan_digest']


def test_changed_or_cancelled_invoice_is_reviewed():
    assert 'invoice_change_review_required' in plan([invoice(accepted_revision='v0')])['rows'][0]['blockers']
    row=plan([invoice(invoice_state='cancelled')])['rows'][0]
    assert 'invoice_state_review_required' in row['blockers']
    assert row['expense_delta'] is None and row['reserve_delta'] is None


@pytest.mark.parametrize('changes',[{'tenant_id':2},{'shop_id':'other'},{'customer_id':'other'}])
def test_cross_scope_rejected(changes):
    with pytest.raises(ValueError,match='scope'):
        plan([invoice(**changes)])


def test_duplicate_source_identity_and_reused_replacement_rejected():
    with pytest.raises(ValueError,match='Duplicate'):
        plan([invoice(),invoice()])
    old=LegacyReplacement(repair_id=1,tenant_id=1,asset_id=1,cost=D('0.00'),confirmed=True)
    with pytest.raises(ValueError,match='replacement'):
        plan([invoice(replacements=(old,)),invoice(repair_order_id='ro2',invoice_id='i2',replacements=(old,))])


def test_paid_amount_cannot_exceed_invoice_or_omit_evidence():
    for amount,ref in [(D('1001.00'),'owner'),(D('200.00'),'')]:
        p=RecordedPayment(amount=amount,paid_on=date(2026,5,1),evidence_ref=ref)
        with pytest.raises(ValueError):plan([invoice(payments=(p,),payments_confirmed=True)])


def test_missing_payment_date_policy_is_rejected():
    with pytest.raises(ValueError,match='payment dates'):
        preview_financial_import(tenant_id=1,shop_id='shop',customer_id='customer',
            invoices=[invoice()],reserve_date_basis=None)


def test_payment_based_reserves_cannot_be_backdated_to_repair_date():
    with pytest.raises(ValueError,match='payment dates'):
        preview_financial_import(tenant_id=1,shop_id='shop',customer_id='customer',
            invoices=[invoice()],reserve_timing='recorded_payments',reserve_date_basis='repair_date')


def test_replacement_from_another_business_rejected():
    old=LegacyReplacement(repair_id=123,tenant_id=2,asset_id=1,cost=D('0.00'),confirmed=True)
    with pytest.raises(ValueError,match='scope'):
        plan([invoice(replacements=(old,))])
